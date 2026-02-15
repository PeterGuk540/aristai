const fs = require("fs");
  const path = require("path");
  const { chromium } = require("playwright");

  (async () => {
    const outDir = path.resolve("tmp/upp-capture/out");
    fs.mkdirSync(outDir, { recursive: true });

    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto("https://campusvirtual.politecnica.edu.pe/aula-virtual.asp", { waitUntil: "domcontentloaded" });
    console.log("Please login manually, then press ENTER here in terminal...");
    await new Promise((resolve) => process.stdin.once("data", resolve));

    const urls = [
      "https://campusvirtual.politecnica.edu.pe/coordinador/carreras.asp",
      "https://campusvirtual.politecnica.edu.pe/coordinador/inicio.asp?carcodi=25",
      "https://campusvirtual.politecnica.edu.pe/coordinador/curso_detalle.asp",
      "https://campusvirtual.politecnica.edu.pe/coordinador/fileManager/syllabus.asp",
      "https://campusvirtual.politecnica.edu.pe/coordinador/linkManager/educationalContent.asp?semana=1"
    ];

    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      await page.goto(url, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1200);

      const html = await page.content();
      const links = await page.$$eval("a", as =>
        as.map(a => ({
          text: (a.textContent || "").trim(),
          href: a.getAttribute("href"),
          onclick: a.getAttribute("onclick")
        }))
      );

      fs.writeFileSync(path.join(outDir, `page-${i + 1}.html`), html, "utf8");
      fs.writeFileSync(path.join(outDir, `page-${i + 1}-links.json`), JSON.stringify({ url, links }, null, 2), "utf8");
    }

    console.log("Done. Files saved in tmp/upp-capture/out");
    await browser.close();
  })();
