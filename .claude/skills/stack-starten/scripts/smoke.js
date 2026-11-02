// Browser-Rauchtest gegen laufende Dienste (Web :3000, API :8000).
// Aufruf: node .claude/skills/stack-starten/scripts/smoke.js   (SMOKE_OUT=Ordner für Screenshots)
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const WEB = process.env.WEB_URL || "http://localhost:3000";
const OUT = process.env.SMOKE_OUT || process.cwd();
const ROOT = path.resolve(__dirname, "../../../..");
const PY = path.join(ROOT, "services/civic-core/.venv/bin/python");

(async () => {
  const formPdf = path.join(OUT, "smoke-form.pdf");
  execFileSync(PY, ["-c", `import sys; sys.path.insert(0, 'tests'); from make_form import make_form_pdf; open(${JSON.stringify(formPdf)}, 'wb').write(make_form_pdf())`], {
    cwd: path.join(ROOT, "services/civic-core"),
  });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(WEB);
  await page.fill("#question", "Was bedeutet § 60 SGB I?");
  await page.press("#question", "Enter");
  await page.waitForSelector("text=Gesetzeszitat", { timeout: 30000 });
  await page.screenshot({ path: path.join(OUT, "smoke-answer.png") });
  console.log("✓ Frage beantwortet");

  await page.goto(WEB);
  await page.setInputFiles("#assistant-chat input[type=file]", formPdf);
  await page.waitForSelector("text=ausfüllbare Felder erkannt");
  console.log("✓ Formular erkannt");
  await (await page.$("#assistant-chat")).screenshot({ path: path.join(OUT, "smoke-agents.png") });

  await browser.close();
  if (errors.length) {
    console.error("JS-Fehler auf der Seite:", errors);
    process.exit(1);
  }
  console.log(`Screenshots in ${OUT}`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
