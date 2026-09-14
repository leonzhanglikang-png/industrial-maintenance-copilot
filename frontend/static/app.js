const $ = (selector) => document.querySelector(selector);
const examples = {
  pressure: "What should I inspect when discharge pressure is low?",
  temperature: "What should be checked when bearing temperature is too high?",
  unrelated: "How do I photograph a distant galaxy?",
};
const toolLabels = {
  search_maintenance_knowledge: "检索手册并生成引用回答",
  lookup_fault_history: "查询设备故障历史",
  analyze_sensor_ranges: "分析传感器读数范围",
};
let config;
let accessToken = "";
let sensorSequence = 0;

function status(selector, text, kind = "") {
  const target = $(selector);
  target.textContent = text;
  target.className = `request-status ${kind}`;
}

function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 180000);
  const headers = new Headers(options.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  try {
    const response = await fetch(`${config.api_prefix}${path}`, {
      ...options, headers, signal: controller.signal,
    });
    const body = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(body.detail)
        ? body.detail.map((item) => `${item.loc.slice(1).join(".")}：${item.msg}`).join("；")
        : (body.detail || "请求失败，请稍后重试。");
      const id = body.request_id || response.headers.get("X-Request-ID");
      throw new Error(`${detail}${id ? `（请求编号 ${id}）` : ""}`);
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("等待超时，请检查服务状态后重试。");
    if (error instanceof TypeError) throw new Error("无法连接服务，请确认后端仍在运行。");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function refreshDocuments() {
  const body = await request("/documents");
  const list = $("#document-list");
  list.replaceChildren();
  for (const document of body.documents) {
    const row = node("li");
    row.append(node("span", "document-source", document.source));
    row.append(node("span", "muted", `${document.chunk_count} 个文本块`));
    list.append(row);
  }
  $("#document-count").textContent = `${body.documents.length} 份文档`;
  $("#storage-status").textContent = "知识库已持久保存 · SQLite";
}

function renderCitation(citation, index, search = false) {
  const card = node("article", "citation-card");
  const title = node("div", "citation-title");
  title.append(node("span", "citation-id", search ? `命中 ${index + 1}` : `[${citation.citation_id}]`));
  title.append(node("span", "", citation.source));
  card.append(title);
  card.append(node("blockquote", "", search ? citation.text : citation.excerpt));
  const page = citation.page_number == null ? "无页码" : `第 ${citation.page_number} 页`;
  card.append(node("div", "citation-meta", `${page} · 排序分数 ${Number(citation.score).toFixed(3)}（非置信度）`));
  return card;
}

function renderResult(body, mode, elapsed) {
  $("#result-empty").hidden = true;
  $("#result-content").hidden = false;
  $("#result-meta").textContent = `耗时 ${(elapsed / 1000).toFixed(2)} 秒`;
  const citations = mode === "search" ? body.results : body.citations;
  const grounded = mode === "agent" ? body.tool_trace[0]?.output.grounded : body.grounded;
  const failed = mode === "agent" && body.stopped_reason === "tool_failure";
  const notice = $("#result-notice");
  notice.className = `result-notice${failed || (mode !== "search" && !grounded) ? " warning" : ""}`;
  if (failed) {
    notice.textContent = "分析中断：工具执行失败。下方仅保留已完成的部分结果，后续工具未执行。";
  } else if (mode === "search") {
    notice.textContent = `找到 ${citations.length} 条候选原文，请核对相关性。`;
  } else if (!grounded) {
    notice.textContent = "没有找到足够的文档依据；请补充手册或调整问题。工具分析结果可另行查看。";
  } else {
    notice.textContent = `回答包含 ${citations.length} 条来源引用，具体结论仍需核验。`;
  }
  if (body.stopped_reason === "step_limit") notice.textContent += " 已达到步数上限，部分工具未执行。";
  $("#answer-text").textContent = mode === "search" ? "" : body.answer;
  $("#citations").replaceChildren(...citations.map((item, index) => renderCitation(item, index, mode === "search")));
  $("#citations-section").hidden = citations.length === 0;
  const traces = body.tool_trace || [];
  $("#trace-section").hidden = traces.length === 0;
  $("#tool-trace").replaceChildren(...traces.map((trace) => {
    const failed = trace.status === "failed";
    const row = node("li", failed ? "tool-failed" : "");
    row.append(node("strong", "", `${trace.step}. ${toolLabels[trace.tool_name] || trace.tool_name} · ${failed ? "执行失败" : "已完成"}`));
    const detail = node("details");
    detail.open = failed;
    detail.append(node("summary", "", "查看执行结果"));
    detail.append(node("pre", "", JSON.stringify(trace.output, null, 2)));
    row.append(detail);
    return row;
  }));
  $("#raw-response").textContent = JSON.stringify(body, null, 2);
}

function addSensor() {
  if ($("#sensor-rows").children.length >= 20) return;
  const id = ++sensorSequence;
  const row = node("div", "sensor-row");
  const fields = node("div", "sensor-fields");
  const descriptors = [
    ["metric", "指标名", "text", "如 bearing_temperature_c"],
    ["value", "数值", "number", "85"],
    ["unit", "单位", "text", "C"],
    ["minimum", "下限（选填）", "number", ""],
    ["maximum", "上限（选填）", "number", "80"],
  ];
  for (const [key, title, type, placeholder] of descriptors) {
    const label = node("label", key === "metric" ? "wide" : "", title);
    const input = node("input");
    input.id = `sensor-${id}-${key}`;
    input.dataset.field = key;
    input.type = type;
    input.placeholder = placeholder;
    if (type === "number") input.step = "any";
    input.required = ["metric", "value", "unit"].includes(key);
    if (key === "metric") input.pattern = "[a-z][a-z0-9_]*";
    if (key === "unit") input.maxLength = 20;
    label.append(input);
    fields.append(label);
  }
  row.append(fields);
  const remove = node("button", "text-button remove-sensor", "移除此读数");
  remove.type = "button";
  remove.addEventListener("click", () => row.remove());
  row.append(remove);
  $("#sensor-rows").append(row);
}

function readSensors() {
  return [...$("#sensor-rows").children].map((row) => {
    const reading = {};
    for (const input of row.querySelectorAll("input")) {
      const value = input.value.trim();
      if (value !== "") reading[input.dataset.field] = input.type === "number" ? Number(value) : value;
    }
    if (reading.minimum === undefined && reading.maximum === undefined) throw new Error("每条传感器读数至少需要一个上下限。");
    if (reading.minimum !== undefined && reading.maximum !== undefined && reading.minimum > reading.maximum) throw new Error("传感器下限不能大于上限。");
    return reading;
  });
}

$("#analysis-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!config) return;
  const query = $("#query").value.trim();
  if (!query) return status("#request-status", "请先输入问题。", "error");
  const mode = $("input[name=mode]:checked").value;
  const button = $("#run-button");
  button.disabled = true;
  status("#request-status", "正在检索和分析，请稍候…");
  const started = performance.now();
  try {
    const limit = Number($("#evidence-limit").value);
    const payload = mode === "search" ? {query, limit} : {query, evidence_limit: limit};
    if (mode === "agent") {
      payload.equipment_id = $("#equipment-id").value.trim() || null;
      payload.sensor_readings = readSensors();
    }
    const path = mode === "agent" ? "/agent/runs" : `/${mode}`;
    const body = await request(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    renderResult(body, mode, performance.now() - started);
    if (body.stopped_reason === "tool_failure") {
      status("#request-status", "分析中断，请查看失败步骤及已保留的部分结果。", "error");
    } else {
      status("#request-status", "分析完成，请查看结果及来源。", "success");
    }
  } catch (error) {
    status("#request-status", error.message, "error");
    if (!$("#result-content").hidden) $("#result-meta").textContent = "上一次成功结果 · 本次请求未完成";
  } finally {
    button.disabled = false;
  }
});

$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("#upload-file").files[0];
  if (!file || !config) return;
  if (file.size > config.max_upload_bytes) return status("#upload-status", "文件超过 5 MiB，请缩小后重试。", "error");
  const button = $("#upload-button");
  button.disabled = true;
  status("#upload-status", "正在解析文档并保存索引…");
  try {
    const data = new FormData();
    data.append("file", file);
    const body = await request("/documents/upload", {method: "POST", body: data});
    status("#upload-status", `${body.source}：生成 ${body.chunk_count} 块，新增 ${body.indexed_chunk_count} 块。${body.indexed_chunk_count === 0 ? "同一内容已在知识库中。" : "已保存，可立即检索。"}`, "success");
    await refreshDocuments();
  } catch (error) {
    status("#upload-status", error.message, "error");
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => {
  $("#query").value = examples[button.dataset.example];
  $("#query").focus();
}));
document.querySelectorAll("input[name=mode]").forEach((input) => input.addEventListener("change", () => {
  const agent = input.value === "agent";
  $("#agent-options").hidden = !agent;
  $("#agent-options").querySelectorAll("input").forEach((field) => { field.disabled = !agent; });
}));
$("#add-sensor").addEventListener("click", addSensor);
$("#unlock").addEventListener("click", async () => {
  accessToken = $("#access-token").value.trim();
  $("#access-token").value = "";
  try {
    await refreshDocuments();
    status("#request-status", "已连接，可以开始分析。", "success");
  } catch (error) { status("#request-status", error.message, "error"); }
});

async function initialize() {
  try {
    const response = await fetch("/app-config");
    if (!response.ok) throw new Error("无法读取工作台配置。");
    config = await response.json();
    await request("/health");
    $("#service-status").textContent = "服务已连接";
    $("#generation-mode").textContent = config.answer_generator === "extractive" ? "本地证据摘录" : "模型辅助回答";
    $("#access-panel").hidden = !config.auth_required;
    $("#run-button").disabled = false;
    $("#upload-button").disabled = false;
    if (config.auth_required) {
      status("#request-status", "请先输入工作台访问口令。");
    } else {
      await refreshDocuments();
      status("#request-status", "选择示例，或输入你的问题。");
    }
  } catch (error) {
    $("#service-status").textContent = "连接需要检查";
    status("#request-status", error.message, "error");
  }
}

initialize();
