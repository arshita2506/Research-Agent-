"use client";

import { useEffect, useState } from "react";
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
const RESEARCH_STATE_KEY = "tripmate-research-state";

// Wrap every table in a scroll container so wide tables never break the layout
function renderMarkdown(text) {
  return marked
    .parse(text)
    .replace(/<table>/g, '<div class="table-wrap"><table>')
    .replace(/<\/table>/g, "</table></div>");
}

export default function Home() {
  const [input, setInput] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Restore the last query/report when returning from a source link or after
  // a browser refresh. sessionStorage is temporary and scoped to this tab.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(RESEARCH_STATE_KEY);
      if (!saved) return;

      const state = JSON.parse(saved);
      if (typeof state.input === "string") setInput(state.input);
      if (typeof state.answer === "string") setAnswer(state.answer);
    } catch {
      sessionStorage.removeItem(RESEARCH_STATE_KEY);
    }
  }, []);

  useEffect(() => {
    if (!input && !answer) return;

    sessionStorage.setItem(
      RESEARCH_STATE_KEY,
      JSON.stringify({ input, answer })
    );
  }, [input, answer]);

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
      <div className="layout">
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
                __html: renderMarkdown(answer),
              }}
            />
          </article>
        )}
      </div>
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

        /* ---------- Layout ---------- */
        .layout {
          display: grid;
          grid-template-columns: 1fr;
          min-height: 100vh;
        }

        .masthead {
          border-bottom: 1px solid var(--rule);
          background: var(--paper);
        }

        .masthead-inner {
          padding: 44px 20px 32px;
        }

        .page-inner {
          width: 100%;
          max-width: 760px;
          margin: 0 auto;
          padding: 32px 20px 80px;
        }

        /* Wide screens: heading on the left, search area on the right */
        @media (min-width: 1000px) {
          .layout {
            grid-template-columns: minmax(340px, 5fr) 7fr;
          }

          .masthead {
            border-bottom: none;
            border-right: 1px solid var(--rule);
          }

          .masthead-inner {
            position: sticky;
            top: 0;
            padding: clamp(56px, 14vh, 140px) clamp(32px, 4vw, 80px);
          }

          .page-inner {
            max-width: none;
            margin: 0;
            padding: clamp(56px, 14vh, 140px) clamp(32px, 5vw, 96px) 100px;
          }

          .page-inner > * {
            max-width: 760px;
          }
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
          font-size: clamp(32px, 3.2vw, 52px);
          line-height: 1.15;
          margin: 10px 0 14px;
          max-width: 16ch;
        }

        .subtitle {
          font-family: "Source Serif 4", Georgia, serif;
          font-size: clamp(17px, 1.3vw, 20px);
          line-height: 1.55;
          color: var(--ink-soft);
          max-width: 40ch;
          margin: 0;
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

        .result-body h1,
        .result-body h2,
        .result-body h3,
        .result-body h4 {
          font-family: "Source Serif 4", Georgia, serif;
          line-height: 1.3;
          margin: 1.8em 0 0.6em;
        }

        .result-body h1 { font-size: 1.7em; }
        .result-body h2 { font-size: 1.4em; }
        .result-body h3 { font-size: 1.2em; }
        .result-body h4 { font-size: 1.05em; }

        .result-body > :first-child {
          margin-top: 0;
        }

        .result-body p {
          margin: 0 0 1.2em;
        }

        .result-body ul,
        .result-body ol {
          margin: 0 0 1.2em;
          padding-left: 1.5em;
        }

        .result-body li {
          margin-bottom: 0.4em;
        }

        .result-body a {
          color: var(--accent);
          text-underline-offset: 3px;
          word-break: break-word;
        }

        .result-body hr {
          border: none;
          border-top: 1px solid var(--rule);
          margin: 2em 0;
        }

        .result-body blockquote {
          margin: 0 0 1.2em;
          padding: 4px 0 4px 16px;
          border-left: 3px solid var(--accent);
          color: var(--ink-soft);
        }

        .result-body code {
          background: var(--accent-soft);
          padding: 2px 5px;
          font-size: 0.9em;
        }

        .result-body pre {
          background: var(--accent-soft);
          border: 1px solid var(--rule);
          padding: 14px 16px;
          overflow-x: auto;
          margin: 0 0 1.2em;
        }

        .result-body pre code {
          background: none;
          padding: 0;
        }

        /* ---------- Tables (report + sources) ---------- */
        .result-body .table-wrap {
          width: 100%;
          overflow-x: auto;
          margin: 0 0 1.6em;
          border: 1px solid var(--rule);
          background: var(--paper-card);
        }

        .result-body table {
          width: 100%;
          border-collapse: collapse;
          font-family: "Inter", -apple-system, sans-serif;
          font-size: 14px;
          line-height: 1.55;
        }

        .result-body th,
        .result-body td {
          padding: 12px 14px;
          text-align: left;
          vertical-align: top;
          border: 1px solid var(--rule);
        }

        .result-body thead th {
          background: var(--accent-soft);
          color: var(--accent);
          font-weight: 600;
          font-size: 13px;
          border-bottom: 2px solid var(--accent);
          white-space: nowrap;
        }

        .result-body tbody tr:nth-child(even) {
          background: var(--paper);
        }

        .result-body tbody tr:hover {
          background: var(--accent-soft);
        }

        .result-body td a {
          word-break: break-all;
        }

        /* remove the outer double border (wrapper already has one) */
        .result-body table tr > :first-child { border-left: none; }
        .result-body table tr > :last-child { border-right: none; }
        .result-body table thead tr:first-child > th { border-top: none; }
        .result-body table tbody tr:last-child > td { border-bottom: none; }

        @media (max-width: 600px) {
          h1 {
            font-size: 30px;
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
