/**
 * Persist research sub-agent state (steps + stats) per session.
 * Survives page refresh so the rolling display isn't lost mid-research.
 */
import type { PerSessionState } from '@/store/agentStore';

/** Max steps to keep in storage and display. Single source of truth. */
export const RESEARCH_MAX_STEPS = 4;

const STORAGE_KEY = 'hf-agent-research';

type ResearchState = {
  steps: string[];
  stats: PerSessionState['researchStats'];
};

type ResearchMap = Record<string, ResearchState>;

function readAll(): ResearchMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeAll(map: ResearchMap): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch { /* quota exceeded — ignore */ }
}

export function saveResearch(
  sessionId: string,
  steps: string[],
  stats: PerSessionState['researchStats'],
): void {
  const map = readAll();
  map[sessionId] = {
    steps: steps.slice(-RESEARCH_MAX_STEPS),
    stats,
  };
  writeAll(map);
}

export function loadResearch(sessionId: string): ResearchState | null {
  const map = readAll();
  return map[sessionId] ?? null;
}

export function clearResearch(sessionId: string): void {
  const map = readAll();
  delete map[sessionId];
  writeAll(map);
}
