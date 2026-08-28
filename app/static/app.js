const $ = (id) => document.getElementById(id);

// 直接打开HTML时使用默认本地服务地址；通过服务访问时跟随当前域名和端口。
if (window.location.protocol !== "file:") {
  $("api-docs-link").href = new URL("/docs", window.location.origin).href;
}

const views = ["recognition", "confirmation", "output", "report"];
const state = {
  description: "",
  recognitionProvider: "api",
  outputProvider: "api",
  candidates: [],
  confirmedType: "",
  databaseMatched: true,
  networkFallbackUsed: false,
  reported: false,
};

const engineeringRules = [
  {
    keywords: ["坑槽", "坑洞", "挖补"],
    candidates: ["沥青路面坑槽修补", "路面局部修复", "沥青路面病害处治"],
  },
  {
    keywords: ["裂缝", "灌缝"],
    candidates: ["路面裂缝灌缝", "路面裂缝处治", "路面病害修复"],
  },
  {
    keywords: ["沥青", "摊铺", "面层"],
    candidates: ["沥青混凝土摊铺", "沥青路面罩面", "路面恢复"],
  },
  {
    keywords: ["护栏", "波形梁"],
    candidates: ["波形梁护栏维修", "交通安全设施维修", "护栏更换"],
  },
];

function selectedValue(name) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value || "api";
}

function providerName(provider) {
  return provider === "api" ? "在线 API" : "本地模型";
}

function setStatus(elementId, message, isError = false) {
  const element = $(elementId);
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function showView(viewName) {
  views.forEach((name) => {
    const active = name === viewName;
    $(`${name}-view`).hidden = !active;
    document.querySelector(`[data-step="${name}"]`).classList.toggle("is-active", active);
  });

  const activeIndex = views.indexOf(viewName);
  document.querySelectorAll(".step").forEach((step, index) => {
    step.classList.toggle("is-complete", index < activeIndex);
  });
}

function buildCandidates(names) {
  return names.map((name, index) => ({
    name,
    score: Math.max(80, Math.floor(Math.random() * 21) + 80 - index * 5),
  }));
}

function findEngineeringCandidates(description) {
  const rule = engineeringRules.find((item) =>
    item.keywords.some((keyword) => description.includes(keyword)),
  );
  return rule ? buildCandidates(rule.candidates) : [];
}

function renderCandidates() {
  $("candidate-list").innerHTML = state.candidates.map((candidate, index) => `
    <label class="candidate-option${index === 0 ? " is-selected" : ""}">
      <input type="radio" name="engineering-candidate" value="${candidate.name}" ${index === 0 ? "checked" : ""}>
      <span class="candidate-name">${candidate.name}</span>
      <span class="match-badge">匹配度 ${candidate.score}%</span>
    </label>
  `).join("");

  document.querySelectorAll(".candidate-option input").forEach((input) => {
    input.addEventListener("change", () => {
      document.querySelectorAll(".candidate-option").forEach((option) => {
        option.classList.toggle("is-selected", option.contains(input));
      });
    });
  });
}

function localOutput(typeName) {
  return `工程类型：${typeName}\n\n参考内容：\n1. 作业前核对现场条件及对应交底资料；\n2. 按已确认的工程类型执行相应养护作业；\n3. 本演示内容为界面占位数据，正式内容将在知识库接入后返回。`;
}

function networkOutput(description) {
  return `检索对象：${description}\n\n网络参考内容：\n当前本地知识库未找到对应工程类型，系统已通过网络搜索获得参考资料。该内容仅用于界面流程验证，正式使用时必须核验来源、适用条件和技术参数。`;
}

function renderOutput() {
  state.outputProvider = selectedValue("output-model");
  const provider = providerName(state.outputProvider);
  $("output-provider-text").textContent = `由 ${provider} 整理`;
  $("confirmed-type-tag").textContent = state.confirmedType || "网络检索工程";
  $("source-badge").textContent = state.networkFallbackUsed ? "网络兜底" : "本地知识库";
  $("source-badge").classList.toggle("source-network", state.networkFallbackUsed);
  $("network-warning").hidden = !state.networkFallbackUsed;
  $("report-button").hidden = !state.networkFallbackUsed || state.reported;
  $("output-content").textContent = state.networkFallbackUsed
    ? networkOutput(state.description)
    : localOutput(state.confirmedType);
}

function runNetworkFallback() {
  state.databaseMatched = false;
  state.networkFallbackUsed = true;
  state.confirmedType = state.description;
  $("candidate-list").innerHTML = "";
  $("confirm-button").hidden = true;
  $("fallback-loading").hidden = false;
  $("confirmation-description").textContent = "本地数据库没有匹配项，系统将自动使用网络搜索兜底。";

  window.setTimeout(() => {
    renderOutput();
    showView("output");
  }, 700);
}

$("match-button").addEventListener("click", () => {
  const description = $("employee-input").value.trim();
  if (!description) {
    setStatus("recognition-status", "请输入施工描述后再进行识别。", true);
    $("employee-input").focus();
    return;
  }

  state.description = description;
  state.recognitionProvider = selectedValue("recognition-model");
  state.candidates = findEngineeringCandidates(description);
  state.databaseMatched = state.candidates.length > 0;
  state.networkFallbackUsed = false;
  state.reported = false;
  $("original-description").textContent = description;
  $("recognition-provider-badge").textContent = `${providerName(state.recognitionProvider)} 识别`;
  $("fallback-loading").hidden = true;
  $("confirm-button").hidden = false;
  $("confirmation-description").textContent = "请根据现场情况选择最符合的标准工程类型。";

  setStatus("recognition-status", "正在识别工程类型...");
  $("match-button").disabled = true;
  window.setTimeout(() => {
    showView("confirmation");
    $("match-button").disabled = false;
    setStatus("recognition-status", "");
    if (state.databaseMatched) {
      renderCandidates();
    } else {
      runNetworkFallback();
    }
  }, 360);
});

$("confirm-button").addEventListener("click", () => {
  const selected = document.querySelector('input[name="engineering-candidate"]:checked');
  if (!selected) return;
  state.confirmedType = selected.value;
  state.networkFallbackUsed = false;
  renderOutput();
  showView("output");
});

$("back-to-recognition").addEventListener("click", () => showView("recognition"));
$("restart-button").addEventListener("click", () => showView("recognition"));

$("regenerate-button").addEventListener("click", () => {
  renderOutput();
  $("regenerate-button").textContent = "整理完成";
  window.setTimeout(() => { $("regenerate-button").textContent = "重新整理"; }, 800);
});

document.querySelectorAll('input[name="output-model"]').forEach((input) => {
  input.addEventListener("change", renderOutput);
});

$("report-button").addEventListener("click", () => {
  $("site-situation").value = state.description;
  $("missing-type").value = state.confirmedType;
  $("issue-description").value = "";
  setStatus("report-status", "");
  showView("report");
});

$("cancel-report").addEventListener("click", () => showView("output"));

$("submit-report").addEventListener("click", () => {
  const siteSituation = $("site-situation").value.trim();
  const missingType = $("missing-type").value.trim();
  const description = $("issue-description").value.trim();
  if (!siteSituation || !missingType || !description) {
    setStatus("report-status", "请完整填写上报信息。", true);
    return;
  }

  window.alert("上报成功");
  state.reported = true;
  $("report-button").hidden = true;
  showView("output");
});
