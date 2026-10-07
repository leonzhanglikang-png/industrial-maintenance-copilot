import { test, expect } from "@playwright/test";

// Opt-in only: records actual local UI/API behavior, never consumes a remote model budget.
test.use({ video: { mode: "on", size: { width: 1440, height: 1050 } } });
test("portfolio demonstration", async ({ page, request }) => {
  test.skip(process.env.RECORD_DEMO !== "1", "Set RECORD_DEMO=1 to record the portfolio walkthrough");
  test.setTimeout(180000);
  const config = await (await request.get("/app-config")).json();
  expect(config.answer_generator).toBe("extractive");
  await page.goto("/");
  await page.locator("#access-token").fill(process.env.API_ACCESS_TOKEN);
  await page.locator("#unlock").click();
  await expect(page.locator("#access-status")).toContainText("已连接");
  async function explain(text, seconds = 10) {
    await page.evaluate((text) => {
      let caption = document.getElementById("recording-caption");
      if (!caption) {
        caption = document.createElement("aside");
        caption.id = "recording-caption";
        caption.style.cssText = "position:fixed;bottom:12px;left:280px;right:24px;padding:14px 22px;background:#102437;color:white;border-radius:10px;z-index:10000;font-size:20px;pointer-events:none";
        document.body.append(caption);
      }
      caption.textContent = text;
    }, text);
    await page.waitForTimeout(seconds * 1000);
  }
  await explain("工业运维助手：查手册、查设备历史、比较输入的传感器读数。本视频使用隔离环境与演示数据。");
  await page.getByRole("link", { name: "02 文档知识库" }).click();
  await explain("文档知识库独立成页：支持文字 PDF、Markdown 和 TXT。解析文字持久保存在 SQLite。");
  await page.locator("#upload-file").setInputFiles({ name: "portfolio-demo.txt", mimeType: "text/plain", buffer: Buffer.from("Inspect the portfolio-demo compressor oil filter before startup.") });
  await page.locator("#upload-button").click();
  await expect(page.locator("#upload-status")).toContainText("已保存");
  await explain("上传后立即建立检索索引；同一内容重复上传不会重复加入。");
  await page.getByRole("link", { name: "01 运维分析" }).click();
  await page.getByRole("button", { name: "出口压力偏低", exact: true }).click();
  await page.locator("#equipment-id").fill("pump-001");
  await page.locator(".sensor-options summary").click();
  await page.locator("#add-sensor").click();
  await page.locator('[data-field="metric"]').fill("bearing_temperature_c");
  await page.locator('[data-field="value"]').fill("85");
  await page.locator('[data-field="unit"]').fill("C");
  await page.locator('[data-field="maximum"]').fill("80");
  await explain("综合分析：输入问题、设备编号及读数。上下限由使用者提供，系统不会推断安全阈值。");
  await page.locator("#run-button").click();
  await expect(page.locator("#request-status")).toContainText("分析完成");
  await explain("回答附原文引用，可核对来源。本录屏使用离线摘录；DeepSeek 的真实回答与费用另有评测报告。");
  await page.locator("#trace-section").scrollIntoViewIfNeeded();
  await explain("工具执行记录展示手册检索、故障历史查询、传感器比较。这是固定受约束流程。");
  await page.locator(".fault-editor summary").click();
  await page.locator("#fault-equipment").fill("portfolio-demo-pump");
  await page.locator("#fault-date").fill("2026-10-07");
  await page.locator("#fault-symptom").fill("演示：压力偏低");
  await page.locator("#fault-cause").fill("演示：吸入过滤器堵塞");
  await page.locator("#fault-action").fill("演示：清理后复测");
  await page.locator("#fault-save").click();
  await expect(page.locator("#fault-status")).toContainText("已保存");
  await explain("维修人员可以录入故障记录。记录保存到数据库，综合分析按设备编号读取。");
  await page.getByText("引用问答", { exact: true }).click();
  await page.getByRole("button", { name: "试试证据不足", exact: true }).click();
  await page.locator("#run-button").click();
  await expect(page.locator("#result-notice")).toContainText("没有找到足够");
  await explain("缺少证据时返回拒答。引用身份校验不能保证所有结论正确，仍需人员核验。");
  await page.getByRole("link", { name: "02 文档知识库" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "删除 portfolio-demo.txt", exact: true }).click();
  await expect(page.locator("#upload-status")).toContainText("已删除");
  await explain("过期手册可删除；文本和索引同步移除，重启也不会重新导入已删除的示例手册。");
  await explain("项目提供公开源码、自动化测试、部署说明、逐题评测及待人工确认的审核表。", 20);
});
