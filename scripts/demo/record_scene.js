// Record one demo scene to demo/raw/*.webm at 1920x1080.
// Usage with the Playwright MCP tool:
//   browser_navigate("about:blank#scene=5")
//   browser_run_code_unsafe(filename="scripts/demo/record_scene.js")
// Needs `make api` + `make web` on a demo DB processed with the live cascade.
// Returns { scene, video, leadMs, seconds, syncMarker }: the scene starts right after the
// magenta sync marker's last frame (leadMs is the wall-clock estimate); keep `seconds`.
async (page) => {
  // Paths are relative to the project root: the Playwright MCP runs this in a vm with no
  // __dirname, and resolves relative paths against the workspace root (as it does filename=).
  const APP = "http://localhost:5173/";
  const SLIDES = "http://localhost:5180/"; // python -m http.server 5180 -d scripts/demo/slides
  const KEY_GAP_MS = 700; // pause after every key, for narration
  const CHAR_DELAY_MS = 120; // per typed character
  const TOAST_HOLD_MS = 120000; // keep "Added to eval set" on screen to the end of scene 6

  // Injected into every page of this recording only; the app itself is unchanged.
  const HARNESS = () => {
    window.__showKey = (label) => {
      let el = document.getElementById("__key_badge");
      if (!el) {
        el = document.createElement("div");
        el.id = "__key_badge";
        el.style.cssText =
          "position:fixed;left:24px;bottom:80px;z-index:99999;padding:8px 14px;border-radius:6px;" +
          "background:#1e2b3c;color:#fff;font:500 20px 'IBM Plex Sans',system-ui,sans-serif;" +
          "transition:opacity 150ms;pointer-events:none";
        document.body.appendChild(el);
      }
      el.textContent = label;
      el.style.opacity = "1";
      clearTimeout(window.__keyBadgeTimer);
      window.__keyBadgeTimer = setTimeout(() => (el.style.opacity = "0"), 1600);
    };
    // The app hides toasts after 2400 ms; the demo holds the eval-set toast for narration.
    const original = window.setTimeout;
    window.setTimeout = function (fn, ms, ...rest) {
      if (ms === 2400 && window.__holdToastMs) ms = window.__holdToastMs;
      return original.call(window, fn, ms, ...rest);
    };
  };

  // about:blank#scene=N[&seconds=S]: S overrides the default scene length (narration retime)
  const params = new URLSearchParams(new URL(page.url()).hash.slice(1));
  const scene = Number(params.get("scene"));
  const secondsOverride = params.has("seconds") ? Number(params.get("seconds")) : null;
  const ctx = await page.context().browser().newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: "demo/raw", size: { width: 1920, height: 1080 } },
  });
  const recordingStart = Date.now();
  await ctx.addInitScript(HARNESS);
  const p = await ctx.newPage();

  const wait = (ms) => p.waitForTimeout(ms);
  const badge = (label) => p.evaluate((l) => window.__showKey && window.__showKey(l), label);
  const press = async (key, label = key, after = KEY_GAP_MS) => {
    await badge(label);
    await p.keyboard.press(key);
    await wait(after);
  };
  const click = async (locator, label, after = KEY_GAP_MS) => {
    await badge(label);
    await locator.click();
    await wait(after);
  };
  const type = async (text, after = KEY_GAP_MS) => {
    await badge(`Type ${text}`);
    await p.keyboard.type(text, { delay: CHAR_DELAY_MS });
    await wait(after);
  };
  const row = (name) => p.getByRole("button", { name });
  const field = (name) => p.getByRole("option", { name: new RegExp(`^${name}`) });
  const tab = (name) => p.getByRole("tab", { name: new RegExp(`^${name}`) });
  const openDesk = async () => {
    await p.goto(APP);
    await p.locator("canvas").first().waitFor();
    await wait(600);
  };
  let visibleAt = 0;
  // Wait until `t` seconds after the scene's first frame, so actions land on narration cues.
  const at = async (t) => {
    const ms = visibleAt + t * 1000 - Date.now();
    if (ms > 0) await wait(ms);
  };
  // Magenta sync box shown during setup and removed at the scene's first frame; the assembler
  // finds its last frame in the raw video and cuts there, so cue times are exact on screen.
  const syncMark = async () => {
    await p.evaluate(() => {
      const m = document.createElement("div");
      m.id = "__sync";
      m.style.cssText = "position:fixed;left:0;top:0;width:24px;height:24px;" +
        "background:#ff00ff;z-index:100000";
      document.body.appendChild(m);
    });
    await wait(400);
    await p.evaluate(() => new Promise((done) => {
      document.getElementById("__sync")?.remove();
      requestAnimationFrame(() => requestAnimationFrame(() => done()));
    }));
  };
  const slide = (file) => p.goto(SLIDES + file).then(() => p.evaluate(() => document.fonts.ready));

  const SCENES = {
    1: { seconds: 30, show: () => slide("01-title.html") },
    2: { seconds: 45, show: () => slide("02-problems.html") },
    3: { seconds: 30, show: () => slide("03-how.html") },
    4: { // review desk overview, on screen from the start; hold
      seconds: 20, show: openDesk,
    },
    5: { // open the clean invoice at 0.5 s; J evenly 4.2 s -> 18.5 s, reaching Total; hold
      seconds: 45,
      show: async () => { await openDesk(); await tab("Approved").click(); await wait(1200); },
      act: async () => {
        await at(0.5);
        await click(row(/Ironclad Security.*4,714\.13/), "Click Ironclad Security");
        await at(2.2);
        await click(field("Vendor"), "Click Vendor"); // start from the first field
        const presses = 8; // Vendor -> Total
        for (let i = 0; i < presses; i++) {
          await at(4.2 + (i * (18.5 - 4.2)) / (presses - 1));
          await press("j", "J", 0);
        }
      },
    },
    6: { // Harbourview: open 0.5 s, invoice date 15.5 s, due date 18.1 s, S 20.7 s; toast to end
      seconds: 50, show: openDesk,
      act: async () => {
        await at(0.5);
        await click(row(/Harbourview Catering/), "Click Harbourview Catering");
        await at(15.0);
        await click(field("Invoice date"), "Click Invoice date", 0);
        await at(15.5);
        await press("Enter", "Enter", 150);
        await press("ControlOrMeta+a", "Select all", 100);
        await type("2026-10-05", 0);
        await press("Enter", "Enter", 0);
        await at(17.6);
        await press("j", "J", 0);
        await at(18.1);
        await press("Enter", "Enter", 150);
        await press("ControlOrMeta+a", "Select all", 100);
        await type("2026-11-04", 0);
        await press("Enter", "Enter", 0);
        await p.evaluate((ms) => (window.__holdToastMs = ms), TOAST_HOLD_MS);
        await at(20.7);
        await press("s", "S", 0);
        await p.getByText("Approved. Added to eval set").waitFor();
      },
    },
    7: { // open Ironclad Security (injection) at 0.5 s; hold
      seconds: 25, show: openDesk,
      act: async () => { await at(0.5); await click(row(/Ironclad Security/), "Click Ironclad Security"); },
    },
    8: { // open Granite Network Systems (arithmetic) at 0.5 s; hold
      seconds: 25,
      show: async () => { await openDesk(); await row(/Cedar & Pine/).click(); await wait(1200); },
      act: async () => {
        await at(0.5);
        await click(row(/Granite Network Systems/), "Click Granite Network Systems");
      },
    },
    9: { // Rejected tab; open the shipping notice at 0.5 s; hold
      seconds: 20,
      show: async () => { await openDesk(); await tab("Rejected").click(); await wait(1200); },
      act: async () => { await at(0.5); await click(row(/doc_018/), "Click shipping notice"); },
    },
    10: { // Evals at 0.5 s; cost vs recall chart at 11.1 s; history line at 23.9 s; hold
      seconds: 45, show: openDesk,
      act: async () => {
        await at(0.5);
        await click(p.getByRole("link", { name: "Evals" }), "Click Evals");
        await p.locator(".recharts-surface").nth(1).waitFor();
        // force: Haiku and Cascade share a point, so one symbol covers the other
        const points = await p.locator(".recharts-scatter-symbol").all();
        for (let i = 0; i < points.length; i++) {
          await at(11.1 + i * 3.2);
          await points[i].hover({ force: true });
        }
        await at(23.9);
        const dots = await p.locator(".recharts-line-dots circle").all();
        await dots[dots.length - 1].hover({ force: true });
      },
    },
    11: { seconds: 35, show: () => slide("11-findings.html") },
    12: { seconds: 30, show: () => slide("12-alternative.html") },
    13: { seconds: 30, show: () => slide("13-process.html") },
    14: { seconds: 30, show: () => slide("14-limits.html") },
    15: { seconds: 15, show: () => slide("15-end.html") },
  };

  const spec = SCENES[scene];
  if (!spec) throw new Error(`unknown scene ${scene}; navigate to about:blank#scene=N first`);
  const seconds = secondsOverride ?? spec.seconds;
  try {
    await spec.show();
    await syncMark();
    visibleAt = Date.now();
    if (spec.act) await spec.act();
    const left = visibleAt + seconds * 1000 - Date.now();
    if (left > 0) await wait(left);
    const overranMs = Math.max(0, -left);
    await ctx.close();
    return {
      scene, seconds, video: await p.video().path(),
      leadMs: visibleAt - recordingStart, overranMs, syncMarker: true,
    };
  } catch (error) {
    await ctx.close();
    throw error;
  }
}
