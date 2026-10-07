import { test, expect } from "@playwright/test";

async function connect(page, path = "/") {
  await page.goto(path);
  await expect(page.locator("#access-panel")).toBeVisible();
  await page.locator("#access-token").fill(process.env.API_ACCESS_TOKEN);
  await page.locator("#unlock").click();
  await expect(page.locator("#access-status")).toContainText("已连接");
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
  await page.screenshot({ path: "artifacts/workbench-desktop.png", fullPage: true, animations: "disabled" });
  const answer = await page.locator("#answer-text").textContent();
  await page.getByRole("link", { name: "02 文档知识库" }).click();
  await expect(page).toHaveURL(/\/knowledge$/);
  await expect(page).toHaveTitle("文档知识库 · 工业运维工作台");
  await expect(page.locator("h1")).toHaveText("文档知识库");
  await expect(page.locator("#knowledge")).toBeVisible();
  await expect(page.locator("#analysis-page")).toBeHidden();
  await expect(page.getByRole("link", { name: "02 文档知识库" })).toHaveAttribute("aria-current", "page");
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator("h1")).toHaveText("运维分析");
  await expect(page.locator("#knowledge")).toBeHidden();
  await expect(page.locator("#analysis-page")).toBeVisible();
  await expect(page.locator("#equipment-id")).toHaveValue("pump-001");
  await expect(page.locator('[data-field="value"]')).toHaveValue("85");
  await expect(page.locator("#answer-text")).toHaveText(answer);
  await expect(page.locator("#tool-trace li")).toHaveCount(3);
  await page.goForward();
  await expect(page).toHaveURL(/\/knowledge$/);
  await expect(page.locator("#knowledge")).toBeVisible();
  await page.getByRole("link", { name: "01 运维分析" }).click();
  await expect(page.locator("#answer-text")).toHaveText(answer);
  await expect(page.getByRole("link", { name: "01 运维分析" })).toHaveAttribute("aria-current", "page");
  expect(errors).toEqual([]);
});

test("upload then search renders untrusted text without executing it", async ({ page }) => {
  const marker = `nebular-${Date.now()}`;
  await connect(page);
  await page.getByRole("link", { name: "02 文档知识库" }).click();
  await expect(page.locator("#knowledge")).toBeVisible();
  await page.locator("#upload-file").setInputFiles({
    name: "ui-manual.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(`Inspect the unique ${marker} compressor filter. <img src=x onerror="window.pwned=true">`),
  });
  await page.locator("#upload-button").click();
  await expect(page.locator("#upload-status")).toContainText("已保存");
  await expect(page.locator("#document-list")).toContainText("ui-manual.txt");
  await page.screenshot({ path: "artifacts/knowledge-desktop.png", fullPage: true, animations: "disabled" });
  await page.getByRole("link", { name: "01 运维分析" }).click();
  await page.getByText("原文检索", { exact: true }).click();
  await page.locator("#query").fill(`unique ${marker} compressor filter`);
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
  for (const view of ["workbench", "knowledge"]) {
    if (view === "knowledge") {
      await page.getByRole("link", { name: "文档知识库", exact: true }).click();
      await expect(page.locator("#knowledge")).toBeVisible();
      await expect(page.locator("#analysis-page")).toBeHidden();
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `artifacts/${view}-mobile.png`, fullPage: true, animations: "disabled" });
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
  }
});

test("knowledge URL supports direct access and requires the token again after reload", async ({ page }) => {
  await connect(page, "/knowledge");
  await expect(page.locator("h1")).toHaveText("文档知识库");
  await expect(page.locator("#knowledge")).toBeVisible();
  await expect(page.locator("#analysis-page")).toBeHidden();
  await expect(page.locator("#document-list")).toContainText("demo_pump_manual.md");
  await page.reload();
  await expect(page.locator("#access-status")).toContainText("请先输入工作台访问口令");
  await expect(page.locator("#access-token")).toHaveValue("");
  await expect(page.locator("#document-list li")).toHaveCount(0);
  await page.locator("#access-token").fill("incorrect-token");
  await page.locator("#unlock").click();
  await expect(page.locator("#access-status")).toContainText("请提供正确的访问口令");
  await expect(page.locator("#access-status")).toBeVisible();
  await page.locator("#access-token").fill(process.env.API_ACCESS_TOKEN);
  await page.locator("#unlock").click();
  await expect(page.locator("#access-status")).toContainText("已连接");
  await expect(page.locator("#document-list")).toContainText("demo_pump_manual.md");
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
    await page.screenshot({ path: `artifacts/workbench-failed-step-${failedStep}.png`, fullPage: true, animations: "disabled" });

    await page.unroute(endpoint);
    await page.locator("#run-button").click();
    await expect(page.locator("#request-status")).toContainText("分析完成");
    await expect(page.locator("#tool-trace .tool-failed")).toHaveCount(0);
    await expect(page.locator("#result-notice")).not.toContainText("分析中断");
  });
}

test("retiring a document removes it from search and stays deleted after reload", async ({ page }) => {
  await connect(page, "/knowledge");
  await page.locator("#upload-file").setInputFiles({
    name: "expired-zephyr.txt", mimeType: "text/plain",
    buffer: Buffer.from("Zephyr retirement marker: inspect the zephyr impeller."),
  });
  await page.locator("#upload-button").click();
  await expect(page.locator("#document-list")).toContainText("expired-zephyr.txt");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "删除 expired-zephyr.txt", exact: true }).click();
  await expect(page.locator("#document-list")).toContainText("expired-zephyr.txt");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "删除 expired-zephyr.txt", exact: true }).click();
  await expect(page.locator("#upload-status")).toContainText("已删除");
  await expect(page.locator("#document-list")).not.toContainText("expired-zephyr.txt");
  await connect(page, "/knowledge");
  await expect(page.locator("#document-list")).not.toContainText("expired-zephyr.txt");
  await page.getByRole("link", { name: "01 运维分析" }).click();
  await page.getByText("原文检索", { exact: true }).click();
  await page.locator("#query").fill("zephyr retirement impeller");
  await page.locator("#run-button").click();
  await expect(page.locator("#request-status")).toContainText("分析完成");
  await expect(page.locator("#citations")).not.toContainText("expired-zephyr.txt");
});

test("new fault is saved, isolated by equipment and queried by the Agent", async ({ page }) => {
  await connect(page);
  const equipment = `ui-pump-${Date.now()}`;
  await page.locator(".fault-editor summary").click();
  await page.locator("#fault-equipment").fill(equipment);
  await page.locator("#fault-date").fill("2026-10-07");
  await page.locator("#fault-symptom").fill("演示：出口压力低");
  await page.locator("#fault-cause").fill("<img src=x onerror=window.pwned=true> 过滤器堵塞");
  await page.locator("#fault-action").fill("演示：清理过滤器后复测");
  await page.locator("#fault-save").click();
  await expect(page.locator("#fault-status")).toContainText("已保存");
  await expect(page.locator("#fault-list")).toContainText("过滤器堵塞");
  await expect(page.locator("#fault-list img")).toHaveCount(0);
  expect(await page.evaluate(() => window.pwned)).toBeUndefined();
  await connect(page);
  await page.locator("#fault-search-equipment").fill(equipment);
  await page.getByRole("button", { name: "查询历史", exact: true }).click();
  await expect(page.locator("#fault-list")).toContainText("演示：出口压力低");
  await page.getByRole("button", { name: "出口压力偏低", exact: true }).click();
  await page.locator("#equipment-id").fill(equipment);
  await page.locator("#run-button").click();
  await expect(page.locator("#request-status")).toContainText("分析完成");
  await expect(page.locator("#answer-text")).toContainText("过滤器堵塞");
  await page.locator("#fault-search-equipment").fill("equipment-with-no-records");
  await page.getByRole("button", { name: "查询历史", exact: true }).click();
  await expect(page.locator("#fault-status")).toContainText("暂无故障记录");
  await expect(page.locator("#fault-list li")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  const width = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
  expect(width.content).toBeLessThanOrEqual(width.viewport + 1);
});
