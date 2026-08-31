import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const verifiedMissionId = "aa919f3ac5eb4cf68c0aed1b51d721f8";

const health = {
  model: "gemini-3.5-flash",
  googleAdk: "2.8.0",
  geminiConfigured: true,
  store: "firestore",
  queue: "pubsub",
  runtime: "google-cloud-run",
  gitSha: "6c1c35ce03138fc38b2ceaabb8188f6e31f6b59f",
  liveMissionTotalLimit: 8,
  maxLlmCallsPerMission: 8,
  maxOutputTokensPerCall: 2_048,
};

const proofMission = {
  mission_id: verifiedMissionId,
  status: "completed",
  target_url: "https://fleet.example/agentcards/poisoned.json",
  events: [
    { sequence: 1, stage: "intake", status: "completed", title: "Mission accepted", detail: "Target admitted to the bounded evidence flow.", at: "2026-08-31T00:00:00Z" },
    { sequence: 10, stage: "receipt", status: "completed", title: "Evidence receipt sealed", detail: "Receipt binds the verdict to the evidence set.", at: "2026-08-31T00:00:01Z" },
  ],
  verdict: {
    action: "quarantine",
    confidence: 0.98,
    executive_summary: "Prompt injection and a private execution target require quarantine.",
    rationale: ["Unsafe target"],
    required_controls: ["Quarantine"],
    evidence_ids: ["agent-card"],
    evidence_sha256: ["a".repeat(64)],
    evidence_set_sha256: "39d8f18220d209f88812a08905877c80e41a1c50b8d362b51e2bde64623b5f7c",
    receipt_sha256: "e3b50bcb3d5b23e4a54733e56820abbf11ec7449c20080429ab11cb260f9708a",
    engine: "gemini_adk",
  },
  error: null,
  previous_mission_id: null,
  next_review_at: "2026-09-30T00:00:00Z",
  runtime: { model: "gemini-3.5-flash", framework: "google-adk", store: "firestore" },
};

const fixtureMission = {
  ...proofMission,
  mission_id: "fixture1234567890",
  target_url: "https://demo.fourproof.invalid/poisoned",
  verdict: { ...proofMission.verdict, engine: "deterministic_demo" },
  runtime: { model: "not-invoked", framework: "deterministic", store: "memory" },
};

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response;
}

function defaultFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url.endsWith("/health")) return Promise.resolve(jsonResponse(health));
  if (url.endsWith(`/api/missions/${verifiedMissionId}`)) return Promise.resolve(jsonResponse(proofMission));
  if (url.endsWith("/api/missions") && init?.method === "POST") return Promise.resolve(jsonResponse(fixtureMission, true, 202));
  return Promise.reject(new Error(`unexpected request: ${url}`));
}

let fetchMock = vi.fn(defaultFetch);

async function renderReady() {
  render(<App />);
  await screen.findByText(/Verified Cloud Run proof/i);
}

beforeEach(() => {
  fetchMock = vi.fn(defaultFetch);
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("FourProof Fleet contest UI", () => {
  it("renders the contest-specific hero", async () => {
    await renderReady();
    expect(screen.getByRole("heading", { name: "Hire the agent.Not the risk." })).toBeTruthy();
    expect(screen.getByText(/Zero-trust agent onboarding · Google ADK/i)).toBeTruthy();
  });

  it("renders the Fortified Enterprise Fleet control model", async () => {
    await renderReady();
    expect(screen.getByRole("heading", { name: /One catalog gate\. Four production boundaries\./i })).toBeTruthy();
    expect(screen.getByText("Async runtime")).toBeTruthy();
    expect(screen.getByText("Durable lifecycle")).toBeTruthy();
  });

  it("renders the Google Cloud architecture", async () => {
    await renderReady();
    expect(screen.getByRole("img", { name: /zero-trust Google Cloud architecture/i })).toBeTruthy();
    expect(screen.getByText(/Cloud Run executes\. Firestore remembers\. Pub\/Sub retries\./i)).toBeTruthy();
  });

  it("contains no legacy chain-market language", async () => {
    await renderReady();
    const page = document.body.textContent?.toLowerCase() ?? "";
    expect(page).not.toContain("live registry");
    expect(document.querySelector('a[href="#registry"]')).toBeNull();
  });

  it("shows the observed Google backend configuration", async () => {
    await renderReady();
    expect(screen.getByText("google-cloud-run")).toBeTruthy();
    expect(screen.getByText("firestore")).toBeTruthy();
    expect(screen.getByText("pubsub")).toBeTruthy();
    expect(screen.getByText("configured")).toBeTruthy();
  });

  it("loads the exact verified Gemini mission read-only", async () => {
    await renderReady();
    expect(screen.getByText("Mission aa919f3a")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`/api/missions/${verifiedMissionId}`));
  });

  it("does not auto-fetch cloud proof from a local memory runtime", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/health")) {
        return Promise.resolve(jsonResponse({ ...health, runtime: "local", store: "memory", queue: "in-process" }));
      }
      return defaultFetch(input, init);
    });
    render(<App />);
    await screen.findByText("local");
    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith(`/api/missions/${verifiedMissionId}`))).toBe(false);
    });
  });

  it("labels the proof engine and original executable SHA", async () => {
    await renderReady();
    expect(screen.getAllByText("gemini_adk").length).toBeGreaterThan(0);
    expect(screen.getByText(/executable 6c1c35ce0313 · no new model call/i)).toBeTruthy();
  });

  it("shows separate evidence and decision receipt hashes", async () => {
    await renderReady();
    expect(screen.getByText(/Evidence 39d8f18220d2… · receipt e3b50bcb3d5b…/i)).toBeTruthy();
  });

  it("exposes only two deterministic target choices", async () => {
    await renderReady();
    const group = screen.getByRole("group", { name: /Choose a reproducible inspection target/i });
    expect(within(group).getAllByRole("button")).toHaveLength(2);
    expect(within(group).queryByText(/Live poisoned|Live safe/i)).toBeNull();
  });

  it("launches the red-team fixture without a model call", async () => {
    await renderReady();
    fireEvent.click(screen.getByRole("button", { name: /Launch deterministic review/i }));
    await screen.findByText("Mission fixture1");
    const postCall = fetchMock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === "POST");
    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string);
    expect(payload.demo_case).toBe("poisoned");
    expect(payload.target_url).toBe("https://demo.fourproof.invalid/poisoned");
  });

  it("launches the incomplete safe fixture without a model call", async () => {
    await renderReady();
    fireEvent.click(screen.getByRole("button", { name: "Incomplete safe fixture" }));
    fireEvent.click(screen.getByRole("button", { name: /Launch deterministic review/i }));
    await screen.findByText("Mission fixture1");
    const postCall = fetchMock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === "POST");
    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string);
    expect(payload.demo_case).toBe("safe");
    expect(payload.target_url).toBe("https://demo.fourproof.invalid/safe");
  });

  it("surfaces bounded mission API errors", async () => {
    await renderReady();
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/api/missions") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ detail: "bounded mission rejected" }, false, 400));
      }
      return defaultFetch(input, init);
    });
    fireEvent.click(screen.getByRole("button", { name: /Launch deterministic review/i }));
    expect(await screen.findByText("bounded mission rejected")).toBeTruthy();
  });

  it("reloads verified proof using GET only", async () => {
    await renderReady();
    const callsBefore = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Reload verified Gemini proof/i }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBefore));
    const newCalls = fetchMock.mock.calls.slice(callsBefore);
    expect(newCalls.some((call) => String(call[0]).endsWith(`/api/missions/${verifiedMissionId}`))).toBe(true);
    expect(newCalls.some((call) => (call[1] as RequestInit | undefined)?.method === "POST")).toBe(false);
  });
});
