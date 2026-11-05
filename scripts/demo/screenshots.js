// README screenshots at 1440x900, deviceScaleFactor 2.
// Run with the Playwright MCP tool: browser_run_code_unsafe(filename="scripts/demo/screenshots.js")
// Needs `make api` and `make web` running against a processed demo DB.
async (page) => {
  // Paths are relative to the project root: the Playwright MCP runs this in a vm with no
  // __dirname, and resolves relative paths against the workspace root (as it does filename=).
  const APP = "http://localhost:5173/";
  const ctx = await page.context().browser().newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const p = await ctx.newPage();
  try {
    // Review desk: Granite Network Systems with Total selected and the connector drawn.
    await p.goto(APP);
    await p.getByRole("button", { name: /Granite Network Systems/ }).click();
    await p.locator("canvas").first().waitFor();
    await p.getByRole("option", { name: /^Total/ }).click();
    await p.locator("svg.fixed path").waitFor();
    await p.waitForTimeout(800); // connector draws in about 250 ms; PDF scroll settles
    await p.screenshot({ path: "docs/review-desk.png" });

    // Evals page.
    await p.goto(`${APP}#/evals`);
    await p.locator(".recharts-surface").nth(1).waitFor();
    await p.waitForTimeout(500);
    await p.screenshot({ path: "docs/evals.png" });

    const selected = await p.evaluate(() => location.hash);
    return { saved: ["docs/review-desk.png", "docs/evals.png"], lastPage: selected };
  } finally {
    await ctx.close();
  }
}
