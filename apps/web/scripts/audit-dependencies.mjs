/**
 * NEXUS temporary, fail-closed npm audit policy.
 * Approved by the owner on 2026-11-18; valid through 2026-12-18 UTC.
 * Never accepts an unrelated high/critical finding or a changed dependency tree.
 * Raw npm audit JSON is printed to the CI log for review.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const ADVISORY = "GHSA-fc5q-39xc-vjpf";
const URL = "https://github.com/advisories/" + ADVISORY;
const EXPIRES_AT = Date.parse("2026-12-19T00:00:00Z");
const EXPECTED = new Map([
  ["picomatch", "4.0.7"],
  ["fdir", "6.5.0"],
  ["tinyglobby", "0.2.17"],
  ["vite", "7.3.8"],
  ["vitest", "5.1.0"],
]);
const fail = (reason) => {
  console.error("[NEXUS audit policy] FAIL: " + reason);
  process.exit(1);
};

const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(npm, ["audit", "--json", "--audit-level=high"], {
  encoding: "utf8",
  maxBuffer: 10 * 1024 * 1024,
  windowsHide: true,
});
if (result.stdout) process.stdout.write(result.stdout);
if (result.stderr) process.stderr.write(result.stderr);
if (result.error || ![0, 1].includes(result.status)) {
  fail("npm audit could not run successfully");
}
let report;
try {
  report = JSON.parse(result.stdout);
} catch {
  fail("npm audit did not produce valid JSON");
}
if (!report || !report.metadata || !report.vulnerabilities ||
    typeof report.vulnerabilities !== "object" || Array.isArray(report.vulnerabilities)) {
  fail("Unexpected npm audit report schema; cannot evaluate findings safely");
}

const severe = Object.entries(report.vulnerabilities)
  .filter(([, finding]) => ["high", "critical"].includes(finding.severity));

if (severe.length === 0) {
  if (result.status !== 0) fail("npm audit failed without an identified severe finding");
  console.log("[NEXUS audit policy] PASS: no high or critical dependency findings");
  process.exit(0);
}
if (Date.now() >= EXPIRES_AT) fail("Temporary exception expired at end of 2026-12-18 UTC");

let advisoryFound = false;
for (const [name, version] of EXPECTED) {
  const item = JSON.parse(readFileSync("package-lock.json", "utf8")).packages["node_modules/" + name];
  if (!item || item.version !== version || item.dev !== true) {
    fail("Approved development-only dependency tree changed: " + name);
  }
}
for (const [name, finding] of severe) {
  if (!EXPECTED.has(name) || finding.severity !== "high" ||
      !Array.isArray(finding.nodes) || finding.nodes.length !== 1 ||
      finding.nodes[0] !== "node_modules/" + name ||
      !Array.isArray(finding.via) || finding.via.length === 0) {
    fail("Unapproved severe finding or changed dependency path: " + name);
  }
  for (const via of finding.via) {
    if (typeof via === "string") {
      if (!EXPECTED.has(via) || !report.vulnerabilities[via]) {
        fail("Unapproved transitive advisory via " + String(via));
      }
    } else if (via && typeof via === "object") {
      if (via.name !== "picomatch" || via.url !== URL || via.severity !== "high") {
        fail("Additional or changed advisory in " + name);
      }
      advisoryFound = true;
    } else {
      fail("Unknown advisory format in " + name);
    }
  }
}
if (!advisoryFound || !severe.some(([name]) => name === "picomatch")) {
  fail("Expected advisory root was not confirmed");
}
console.warn("[NEXUS audit policy] TEMPORARY EXCEPTION: " + ADVISORY +
  " in the exact development-only Vite/Vitest tree; expires 2026-12-18 UTC.");
console.warn("[NEXUS audit policy] All other high/critical findings remain blocking.");
