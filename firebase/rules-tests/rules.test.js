// Firestore Security Rules tests (judge check: status cannot be changed without admin access).
// Run:  firebase emulators:exec --only firestore "npm --prefix firebase/rules-tests test"
import { readFileSync } from "node:fs";
import { test, before, after, beforeEach } from "node:test";
import { assertFails, assertSucceeds, initializeTestEnvironment } from "@firebase/rules-unit-testing";
import { doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs } from "firebase/firestore";

let env;
before(async () => {
  env = await initializeTestEnvironment({
    projectId: "rastaai-e99f8",
    firestore: { rules: readFileSync(new URL("../firestore.rules", import.meta.url), "utf8"), host: "127.0.0.1", port: 8080 },
  });
});
after(async () => env.cleanup());
beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, "reports/RA-AAAAAA"), { category: "pothole", status: "pending", reporterUid: "citizen" });
    await setDoc(doc(db, "clusters/C-AAAAAA"), { category: "pothole", reportCount: 1 });
    await setDoc(doc(db, "reportImages/RA-AAAAAA"), { jpeg: "x" });
    await setDoc(doc(db, "rateLimits/submit_uid_citizen"), { count: 1 });
  });
});

const anon = () => env.authenticatedContext("citizen", { firebase: { sign_in_provider: "anonymous" } }).firestore();
const admin = () => env.authenticatedContext("boss", { admin: true }).firestore();
const fakeAdmin = () => env.authenticatedContext("mallory", { admin: "true" }).firestore();
const nobody = () => env.unauthenticatedContext().firestore();

test("citizen cannot change status, create, or delete reports", async () => {
  const db = anon();
  await assertFails(updateDoc(doc(db, "reports/RA-AAAAAA"), { status: "resolved" }));
  await assertFails(setDoc(doc(db, "reports/RA-NEW000"), { category: "pothole", status: "resolved" }));
  await assertFails(deleteDoc(doc(db, "reports/RA-AAAAAA")));
});

test("citizen and unauthenticated users cannot read reports, clusters, images or rate limits", async () => {
  for (const db of [anon(), nobody()]) {
    await assertFails(getDoc(doc(db, "reports/RA-AAAAAA")));
    await assertFails(getDocs(collection(db, "reports")));
    await assertFails(getDocs(collection(db, "clusters")));
    await assertFails(getDoc(doc(db, "reportImages/RA-AAAAAA")));
    await assertFails(getDoc(doc(db, "rateLimits/submit_uid_citizen")));
  }
});

test("a claim that is not boolean true is not admin", async () => {
  await assertFails(getDocs(collection(fakeAdmin(), "reports")));
});

test("admin can read reports and clusters but status still changes only via the API", async () => {
  const db = admin();
  await assertSucceeds(getDoc(doc(db, "reports/RA-AAAAAA")));
  await assertSucceeds(getDocs(collection(db, "clusters")));
  await assertFails(updateDoc(doc(db, "reports/RA-AAAAAA"), { status: "resolved" }));
  await assertFails(getDoc(doc(db, "reportImages/RA-AAAAAA")));
  await assertFails(setDoc(doc(db, "rateLimits/x"), { count: 0 }));
});

test("public/config is readable by anyone but writable by no client", async () => {
  await env.withSecurityRulesDisabled(async (ctx) => setDoc(doc(ctx.firestore(), "public/config"), { apiBase: "https://x" }));
  await assertSucceeds(getDoc(doc(nobody(), "public/config")));
  await assertFails(setDoc(doc(anon(), "public/config"), { apiBase: "https://evil" }));
  await assertFails(setDoc(doc(admin(), "public/config"), { apiBase: "https://evil" }));
  await assertFails(getDoc(doc(nobody(), "public/other")));
});

test("unknown collections are closed", async () => {
  await assertFails(setDoc(doc(admin(), "anything/else"), { a: 1 }));
  await assertFails(getDoc(doc(anon(), "anything/else")));
});
