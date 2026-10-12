// Tidy the recording the visual spec replays (`npm run visual:record` runs this afterwards).
// A recording made against the dev server holds every response twice (React's development
// double-mount) plus the requests that were cancelled along the way. Keep one completed
// response per request, so the file is small and a replay can never pick a cancelled entry.
import { readFileSync, writeFileSync } from "node:fs";

const file = new URL("./visual.har", import.meta.url);
const har = JSON.parse(readFileSync(file, "utf8"));
const byRequest = new Map();
for (const entry of har.log.entries) {
  if (entry.response.status > 0) byRequest.set(`${entry.request.method} ${entry.request.url}`, entry);
}
har.log.entries = [...byRequest.values()];
har.log.pages = [];
writeFileSync(file, JSON.stringify(har));
console.log(`visual.har: ${har.log.entries.length} responses kept`);
