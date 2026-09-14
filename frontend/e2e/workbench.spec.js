import { test, expect } from "@playwright/test";

async function connect(page) {
  await page.goto("/");
  await expect(page.locator("#access-panel")).toBeVisible();
  await page.locator("#access-token").fill(process.env.API_ACCESS_TOKEN);
  await page.locator("#unlock").click();
  await expect(page.locator("#request-status")).toContainText("已连接");
}

test("three-tool workflow shows answer, citations and trace", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await connect(page);
  await page.getByRole("button", { name: "出口压力偏低" }).click();
  await page.locator("#equipment-id").fill("pump-001");
  await page.locator(".sensor-options summary").click();
  await page.locator("#add-sensor").click();
  await page.locator('[data-field="metric"]').fill("bearing_temperature_c");
  await page.locator('[data-field="value"]').fill("85");
  await page.locator('[data-field="unit"]').fill("C");
  await page.locator('[data-field="maximum"]').fill("80");
  await page.locator("#run-button").click();
  await expect(page.locator("#request-status")).toContainText("分析完成");
  await expect(page.locator("#tool-trace li")).toHaveCount(3);
  await expect(page.locator("#citations")).toContainText("demo_pump_manual.md");
  await expect(page.locator("#answer-text")).toContainText("above_range");
  await expect(page.locator("#access-token")).toHaveValue("");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "artifacts/workbench-desktop.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("upload then search renders untrusted text without executing it", async ({ page }) => {
  await connect(page);
  await page.locator("#upload-file").setInputFiles({
    name: "ui-manual.txt",
    mimeType: "text/plain",
    buffer: Buffer.from('Inspect the unique nebular compressor filter. <img src=x onerror="window.pwned=true">'),
  });
  await page.locator("#upload-button").click();
  await expect(page.locator("#upload-status")).toContainText("已保存");
  await expect(page.locator("#document-list")).toContainText("ui-manual.txt");
  await page.getByText("原文检索", { exact: true }).click();
  await page.locator("#query").fill("unique nebular compressor filter");
  await page.locator("#run-button").click();
  await expect(page.locator("#request-status")).toContainText("分析完成");
  await expect(page.locator("#citations")).toContainText("<img src=x");
  expect(await page.evaluate(() => window.pwned)).toBeUndefined();
  await expect(page.locator("#citations img")).toHaveCount(0);
});

test("mobile view supports insufficient-evidence answers without horizontal scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await connect(page);
  await page.getByText("引用问答", { exact: true }).click();
  await page.locator("#query").fill("quantum entanglement superconducting qubits");
  await page.locator("#run-button").click();
  await expect(page.locator("#result-notice")).toContainText("没有找到足够的文档依据");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "artifacts/workbench-mobile.png", fullPage: true });
  const layout = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflow: Array.from(document.querySelectorAll("body *"))
      .filter((element) => element.getBoundingClientRect().right > window.innerWidth + 1)
      .map((element) => ({
        tag: element.tagName,
        id: element.id,
        className: element.className,
        right: element.getBoundingClientRect().right,
      })),
  }));
  expect(layout.scrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width + 1);
});

for (const failedStep of [1, 2]) {
  test(`tool failure at step ${failedStep} is shown as interrupted, not completed`, async ({ page }) => {
    await connect(page);
    await page.getByRole("button", { name: "出口压力偏低" }).click();
    await page.locator("#equipment-id").fill("pump-001");
    await page.locator("#run-button").click();
    await expect(page.locator("#request-status")).toContainText("分析完成");
    await expect(page.locator("#citations-section")).toBeVisible();

    // Inject the failure response only in this browser test, never in the deployed app.
    const endpoint = "**/api/v1/agent/runs";
    await page.route(endpoint, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.tool_trace = body.tool_trace.slice(0, failedStep);
      const failed = body.tool_trace[failedStep - 1];
      failed.status = "failed";
      failed.output = {
        error_code: failedStep === 1 ? "citation_validation_failed" : "tool_execution_failed",
        message: "工具执行失败，本次分析已停止。",
      };
      body.stopped_reason = "tool_failure";
      body.steps_executed = failedStep;
      body.answer = failedStep === 1 ? "Analysis stopped." : `${body.answer.split("\n\n")[0]}\n\nAnalysis stopped.`;
      if (failedStep === 1) {
        body.citations = [];
        body.generation_method = "failed";
      }
      await route.fulfill({ response, json: body });
    });
    await page.locator("#run-button").click();
    await expect(page.locator("#request-status")).toContainText("分析中断");
    await expect(page.locator("#request-status")).not.toContainText("分析完成");
    await expect(page.locator("#result-notice")).toContainText("部分结果");
    await expect(page.locator("#result-notice")).not.toContainText("没有找到足够");
    await expect(page.locator("#tool-trace li")).toHaveCount(failedStep);
    await expect(page.locator("#tool-trace .tool-failed")).toHaveCount(1);
    await expect(page.locator(".tool-failed strong")).toContainText("执行失败");
    await expect(page.locator(".tool-failed pre")).toBeVisible();
    if (failedStep === 1) {
      await expect(page.locator("#citations-section")).toBeHidden();
      await expect(page.locator("#citations")).toBeEmpty();
    } else {
      await expect(page.locator("#citations")).toContainText("demo_pump_manual.md");
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `artifacts/workbench-failed-step-${failedStep}.png`, fullPage: true });

    await page.unroute(endpoint);
    await page.locator("#run-button").click();
    await expect(page.locator("#request-status")).toContainText("分析完成");
    await expect(page.locator("#tool-trace .tool-failed")).toHaveCount(0);
    await expect(page.locator("#result-notice")).not.toContainText("分析中断");
  });
}
