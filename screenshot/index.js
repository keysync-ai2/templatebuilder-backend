/**
 * Screenshot Lambda — HTML → PNG via Puppeteer.
 *
 * POST /api/screenshot
 * Body: { "html": "<html>...</html>", "width": 600, "height": 800 }
 * Returns: { "png_base64": "..." }
 */

const chromium = require("@sparticuz/chromium");
const puppeteer = require("puppeteer-core");

exports.handler = async (event) => {
  const corsHeaders = {
    "Access-Control-Allow-Origin": process.env.CORS_ORIGIN || "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
  };

  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: corsHeaders, body: "" };
  }

  let body;
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    return {
      statusCode: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ error: { code: "PARSE_ERROR", message: "Invalid JSON body" } }),
    };
  }

  const { html, width = 600, height = 800 } = body;
  if (!html) {
    return {
      statusCode: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ error: { code: "VALIDATION_ERROR", message: "html is required" } }),
    };
  }

  let browser;
  try {
    browser = await puppeteer.launch({
      args: chromium.args,
      defaultViewport: { width: Number(width), height: Number(height) },
      executablePath: await chromium.executablePath(),
      headless: chromium.headless,
    });

    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0", timeout: 15000 });
    const screenshot = await page.screenshot({ type: "png", fullPage: true });
    const png_base64 = screenshot.toString("base64");

    return {
      statusCode: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ png_base64, size_bytes: screenshot.length }),
    };
  } catch (err) {
    return {
      statusCode: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ error: { code: "RENDER_ERROR", message: err.message } }),
    };
  } finally {
    if (browser) await browser.close();
  }
};
