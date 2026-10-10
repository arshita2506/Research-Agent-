"use client";

import { useState } from "react";
import { marked } from "marked";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL;
const API_URL = configuredApiUrl
  ? `${configuredApiUrl.replace(/\/$/, "")}/api/research`.replace(
      "/api/research/api/research",
      "/api/research"
    )
  : "http://127.0.0.1:8000/api/research";
const QUICK_PROMPTS = [
  "Impact of Artificial Intelligence on software development",
  "Latest research on Large Language Models",
  "How does Retrieval Augmented Generation work?",
];

export default function Home() {
  const [input, setInput] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");


  // -----------------------------
  // Start Research
  // -----------------------------

async function research() {
  if (!input.trim() || loading) return;

  setLoading(true);
  setError("");

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: input,
      }),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok || data.success === false) {
      throw new Error(
        data.error ||
          (typeof data.detail === "string" ? data.detail : "Research failed.")
      );
    }

    setAnswer(data.answer || "");
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
}

  function handleKeyDown(event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      research();
    }
  }


  return (
    <main className="page">
      <header className="masthead">
        <div className="masthead-inner">
          <span className="kicker">Research desk</span>
          <h1>Ask a question, get it sourced.</h1>
          <p className="subtitle">
            Draws on web sources, academic papers and news, then gives you
            a sourced research report.
          </p>
        </div>
      </header>

      <div className="page-inner">
        {/* Search Box */}
        <section className="query-card">
          <label className="field-label" htmlFor="query">
            Your question
          </label>
          <textarea
            id="query"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What do you want to understand?"
          />
          <div className="query-footer">
            <span className="hint">⌘/Ctrl + Enter to run</span>
            <button
              className="btn-primary"
              onClick={research}
              disabled={loading}
            >
              {loading ? "Researching…" : "Start research"}
            </button>
          </div>
        </section>

        {/* Quick Prompts */}
        <section className="prompts">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              className="prompt-chip"
              onClick={() => setInput(prompt)}
            >
              {prompt}
            </button>
          ))}
        </section>

        {/* Error */}
        {error && (
          <div className="error" role="alert">
            <span className="error-label">Something went wrong</span>
            <p>{error}</p>
          </div>
        )}

        {/* Research Result */}
        {answer && (
          <article className="result">
            <div className="result-heading">
              <span className="kicker">Report</span>
              <h2>Findings</h2>
            </div>

            <div
              className="result-body"
              dangerouslySetInnerHTML={{
                __html: marked.parse(answer),
              }}
            />

          </article>
        )}
      </div>

      <style jsx global>{`
        @import url("https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;500;600&display=swap");

        :root {
          --paper: #faf9f6;
          --paper-card: #ffffff;
          --ink: #1c1b1a;
          --ink-soft: #5c584f;
          --rule: #e2ded3;
          --accent: #1f5f5b;
          --accent-soft: #e5efed;
          --danger: #8c2f1f;
          --danger-soft: #f7eae7;
        }

        * {
          box-sizing: border-box;
        }

        body {
          margin: 0;
          background: var(--paper);
          color: var(--ink);
          font-family: "Inter", -apple-system, sans-serif;
        }

        .page {
          min-height: 100vh;
        }

        .masthead {
          border-bottom: 1px solid var(--rule);
          background: var(--paper);
        }

        .masthead-inner {
          max-width: 680px;
          margin: 0 auto;
          padding: 64px 24px 40px;
        }

        .kicker {
          font-family: "Inter", sans-serif;
          font-size: 13px;
          font-weight: 600;
          color: var(--accent);
          letter-spacing: 0.02em;
        }

        h1 {
          font-family: "Source Serif 4", Georgia, serif;
          font-weight: 600;
          font-size: 40px;
          line-height: 1.15;
          margin: 10px 0 14px;
          max-width: 14ch;
        }

        .subtitle {
          font-family: "Source Serif 4", Georgia, serif;
          font-size: 18px;
          line-height: 1.55;
          color: var(--ink-soft);
          max-width: 46ch;
          margin: 0;
        }

        .page-inner {
          max-width: 680px;
          margin: 0 auto;
          padding: 40px 24px 100px;
        }

        .field-label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: var(--ink-soft);
          margin-bottom: 8px;
        }

        .query-card {
          background: var(--paper-card);
          border: 1px solid var(--rule);
          padding: 24px;
        }

        textarea {
          width: 100%;
          min-height: 110px;
          padding: 14px;
          box-sizing: border-box;
          border: 1px solid var(--rule);
          background: var(--paper);
          color: var(--ink);
          font-family: "Inter", sans-serif;
          font-size: 15px;
          line-height: 1.5;
          resize: vertical;
        }

        textarea:focus,
        button:focus-visible {
          outline: 2px solid var(--accent);
          outline-offset: 2px;
        }

        .query-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 14px;
        }

        .hint {
          font-size: 13px;
          color: var(--ink-soft);
        }

        button {
          font-family: "Inter", sans-serif;
          cursor: pointer;
        }

        button:disabled {
          cursor: not-allowed;
          opacity: 0.55;
        }

        .btn-primary {
          background: var(--ink);
          color: var(--paper);
          border: 1px solid var(--ink);
          padding: 11px 20px;
          font-size: 14px;
          font-weight: 500;
        }

        .btn-primary:hover:not(:disabled) {
          background: var(--accent);
          border-color: var(--accent);
        }

        .btn-secondary {
          margin-top: 12px;
          background: transparent;
          color: var(--ink);
          border: 1px solid var(--rule);
          padding: 10px 18px;
          font-size: 14px;
          font-weight: 500;
        }

        .btn-secondary:hover:not(:disabled) {
          border-color: var(--ink);
        }

        .btn-approve {
          background: var(--accent);
          color: #fff;
          border: 1px solid var(--accent);
          padding: 10px 18px;
          font-size: 14px;
          font-weight: 500;
        }

        .btn-approve:hover:not(:disabled) {
          background: #174a47;
        }

        .prompts {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin: 20px 0 0;
        }

        .prompt-chip {
          background: transparent;
          border: 1px solid var(--rule);
          color: var(--ink-soft);
          padding: 8px 14px;
          font-size: 13px;
        }

        .prompt-chip:hover {
          border-color: var(--accent);
          color: var(--accent);
        }

        .error {
          margin-top: 24px;
          background: var(--danger-soft);
          border-left: 3px solid var(--danger);
          padding: 14px 16px;
        }

        .error-label {
          display: block;
          font-size: 13px;
          font-weight: 600;
          color: var(--danger);
          margin-bottom: 4px;
        }

        .error p {
          margin: 0;
          font-size: 14px;
          color: var(--ink);
        }

        .result {
          margin-top: 48px;
          border-top: 1px solid var(--rule);
          padding-top: 32px;
        }

        .result-heading h2 {
          font-family: "Source Serif 4", Georgia, serif;
          font-size: 26px;
          margin: 6px 0 24px;
        }

        .result-body {
          font-family: "Source Serif 4", Georgia, serif;
          font-size: 17px;
          line-height: 1.75;
          color: var(--ink);
        }

        .result-body :global(h1),
        .result-body :global(h2),
        .result-body :global(h3) {
          font-family: "Source Serif 4", Georgia, serif;
          line-height: 1.3;
        }

        .result-body :global(p) {
          margin: 0 0 1.2em;
        }

        .result-body :global(a) {
          color: var(--accent);
        }

        .result-body :global(code) {
          background: var(--accent-soft);
          padding: 2px 5px;
          font-size: 0.9em;
        }

        @media (max-width: 600px) {
          h1 {
            font-size: 30px;
          }

          .masthead-inner {
            padding: 44px 20px 32px;
          }

          .query-footer {
            flex-direction: column;
            align-items: stretch;
            gap: 12px;
          }

          .btn-primary {
            width: 100%;
          }
        }
      `}</style>
    </main>
  );

}
