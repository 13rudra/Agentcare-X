/**
 * AgentCare X — Interactive Dashboard Application
 *
 * Connects to the FastAPI backend and drives mock/manual episodes
 * with real-time chat, emotion tracking, reward scoring, and final grading.
 *
 * FIX: Dynamic API URL — works on localhost AND HuggingFace Spaces
 */

// ─── Dynamic API Base URL ──────────────────────────────────────────
// On HuggingFace Spaces the app runs at window.location.origin (port 443/80)
// Locally it runs at port 7860
const API = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:7860"
  : window.location.origin;

// ─── State ─────────────────────────────────────────────────────────
let selectedTaskId = null;
let episodeActive = false;
let episodeDone = false;
let currentObs = null;
let emotionHistory = [];
let cumulativeReward = 0;
let turnNumber = 0;
let maxTurns = 10;

// Mock action queues
const MOCK_ACTIONS = {
  easy: [
    { action_type: "respond", message: "I'm sorry for the concern! Let me check your order status right away." },
    { action_type: "call_tool", tool_name: "check_order_status", tool_parameters: { order_id: "ORD-20240315-001" } },
    { action_type: "respond", message: "Your order for Wireless Bluetooth Headphones has been shipped and is estimated to arrive by March 22, 2024. Is there anything else I can help with?" },
  ],
  medium: [
    { action_type: "respond", message: "I'm truly sorry for the delay and I completely understand your frustration. Let me look into this immediately." },
    { action_type: "call_tool", tool_name: "check_order_status", tool_parameters: { order_id: "ORD-20240310-042" } },
    { action_type: "respond", message: "I can see your Smart Fitness Watch order has been delayed. I sincerely apologize for this inconvenience. Let me process a full refund for you right away." },
    { action_type: "call_tool", tool_name: "process_refund", tool_parameters: { order_id: "ORD-20240310-042", reason: "delayed" } },
    { action_type: "respond", message: "Your refund of $149.99 has been initiated and will be reflected in your account within 3-5 business days. I'm sorry again for the trouble." },
  ],
  hard: [
    { action_type: "respond", message: "I am so sorry about this! Receiving the wrong item is completely unacceptable and I understand how frustrating this must be. Let me help resolve this right away." },
    { action_type: "call_tool", tool_name: "check_order_status", tool_parameters: { order_id: "ORD-20240308-117" } },
    { action_type: "respond", message: "I can confirm there was a mistake with your order — you should have received a 15-inch Gaming Laptop but got the wrong item. I sincerely apologize. Let me process a full refund immediately." },
    { action_type: "call_tool", tool_name: "process_refund", tool_parameters: { order_id: "ORD-20240308-117", reason: "wrong_item" } },
    { action_type: "respond", message: "Your refund of $1,299.99 has been initiated. I'm also going to escalate this to our management team to ensure this doesn't happen again." },
    { action_type: "call_tool", tool_name: "escalate_to_manager", tool_parameters: { order_id: "ORD-20240308-117", reason: "wrong_item delivered, customer received headphones instead of laptop" } },
    { action_type: "respond", message: "The case has been escalated (ticket ESC-ORD-20240308-117-001). A manager will follow up within 24 hours. Your refund is processing. I'm truly sorry for this experience." },
  ],
  out_of_stock: [
    { action_type: "respond", message: "I'm really sorry to hear about this! I completely understand how frustrating it must be to find out your order is out of stock. Let me look into this for you right away." },
    { action_type: "call_tool", tool_name: "check_order_status", tool_parameters: { order_id: "ORD-20240320-088" } },
    { action_type: "respond", message: "I can see your 4K Mirrorless Camera order is indeed out of stock. Let me check our inventory for restock dates and alternatives." },
    { action_type: "call_tool", tool_name: "check_inventory", tool_parameters: { product_name: "4K Mirrorless Camera" } },
    { action_type: "respond", message: "Great news — the camera is expected to be restocked by April 15, 2024. We also have two alternatives: a Refurbished model at $719.99 or the Next Gen model at $989.99. If you'd like to wait for the restock, I can apply a discount for the inconvenience. I'm sorry for the trouble!" },
  ],
  subscription: [
    { action_type: "respond", message: "I understand your frustration and I'm sorry you're feeling this way. Let me pull up your subscription details so I can help you find the best solution." },
    { action_type: "call_tool", tool_name: "check_subscription", tool_parameters: { order_id: "SUB-20240201-005" } },
    { action_type: "respond", message: "I can see you're on the Premium Cloud Storage Plan at $29.99/month. You have 18 days remaining in your current billing cycle. If you cancel now, you'd receive a prorated refund of $17.99. However, I'd love to help you stay — would a 20% discount work for you?" },
    { action_type: "call_tool", tool_name: "apply_retention_discount", tool_parameters: { order_id: "SUB-20240201-005", discount_percent: "20" } },
    { action_type: "respond", message: "I've applied a 20% retention discount. Your new monthly price is $23.99 instead of $29.99. I hope this helps! Let me know if there's anything else I can assist you with." },
  ],
};

let mockStepIndex = 0;

// Tool parameter schemas
const TOOL_PARAMS = {
  check_order_status: [{ name: "order_id", placeholder: "ORD-..." }],
  process_refund: [
    { name: "order_id", placeholder: "ORD-..." },
    { name: "reason", placeholder: "e.g. delayed, wrong_item" },
  ],
  escalate_to_manager: [
    { name: "order_id", placeholder: "ORD-..." },
    { name: "reason", placeholder: "Reason for escalation" },
  ],
  check_inventory: [
    { name: "product_name", placeholder: "e.g. 4K Mirrorless Camera" },
  ],
  check_subscription: [
    { name: "order_id", placeholder: "SUB-..." }
  ],
  apply_retention_discount: [
    { name: "order_id", placeholder: "SUB-..." },
    { name: "discount_percent", placeholder: "e.g. 20" }
  ]
};

// ─── DOM References ────────────────────────────────────────────────
const $taskCards = document.getElementById("taskCards");
const $btnStart = document.getElementById("btnStart");
const $btnReset = document.getElementById("btnReset");
const $runMode = document.getElementById("runMode");
const $chatArea = document.getElementById("chatArea");
const $chatPlaceholder = document.getElementById("chatPlaceholder");
const $inputArea = document.getElementById("inputArea");
const $inputRespond = document.getElementById("inputRespond");
const $inputTool = document.getElementById("inputTool");
const $tabRespond = document.getElementById("tabRespond");
const $tabTool = document.getElementById("tabTool");
const $agentMessage = document.getElementById("agentMessage");
const $btnSend = document.getElementById("btnSend");
const $btnToolSend = document.getElementById("btnToolSend");
const $toolSelect = document.getElementById("toolSelect");
const $toolParams = document.getElementById("toolParams");
const $turnCount = document.getElementById("turnCount");
const $maxTurns = document.getElementById("maxTurns");
const $emotionArc = document.getElementById("emotionArc");
const $emotionValue = document.getElementById("emotionValue");
const $rewardValue = document.getElementById("rewardValue");
const $rewardBar = document.getElementById("rewardBar");
const $toolChips = document.getElementById("toolChips");
const $breakdownList = document.getElementById("breakdownList");
const $finalScores = document.getElementById("finalScores");
const $toastContainer = document.getElementById("toastContainer");
const $serverStatus = document.getElementById("serverStatus");
const $serverStatusText = document.getElementById("serverStatusText");

// Info modal elements
const $btnInfoToggle = document.getElementById("btnInfoToggle");
const $infoModalOverlay = document.getElementById("infoModalOverlay");
const $btnInfoClose = document.getElementById("btnInfoClose");

// ─── Initialization ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initParticles();
  checkServerHealth();
  fetchTasks();
  setupEventListeners();
  renderToolParams();
});

// ─── Background Particles ──────────────────────────────────────────
function initParticles() {
  const container = document.getElementById("bgParticles");
  for (let i = 0; i < 30; i++) {
    const p = document.createElement("div");
    p.className = "particle";
    p.style.left = `${Math.random() * 100}%`;
    p.style.top = `${50 + Math.random() * 50}%`;
    p.style.animationDelay = `${Math.random() * 12}s`;
    p.style.animationDuration = `${8 + Math.random() * 8}s`;
    p.style.width = `${1 + Math.random() * 2}px`;
    p.style.height = p.style.width;
    const colors = ["#6366f1", "#a855f7", "#ec4899", "#3b82f6"];
    p.style.background = colors[Math.floor(Math.random() * colors.length)];
    container.appendChild(p);
  }
}

// ─── Server Health Check ──────────────────────────────────────────
async function checkServerHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    if (data.status === "ok") {
      $serverStatus.className = "status-dot online";
      $serverStatusText.textContent = "Server Online";
    } else {
      $serverStatus.className = "status-dot offline";
      $serverStatusText.textContent = "Server Offline";
    }
  } catch {
    $serverStatus.className = "status-dot offline";
    $serverStatusText.textContent = "Server Offline";
    // Retry after 5 seconds
    setTimeout(checkServerHealth, 5000);
  }
}

// ─── Fetch Tasks ──────────────────────────────────────────────────
async function fetchTasks() {
  try {
    const res = await fetch(`${API}/tasks`);
    const tasks = await res.json();
    renderTaskCards(tasks);
  } catch (e) {
    toast("Failed to load tasks from server", "error");
  }
}

function renderTaskCards(tasks) {
  $taskCards.innerHTML = "";
  tasks.forEach((t) => {
    const card = document.createElement("div");
    card.className = "task-card";
    card.dataset.taskId = t.task_id;
    card.innerHTML = `
      <div class="task-card-header">
        <span class="task-title">${capitalize(t.task_id)} Task</span>
        <span class="diff-badge ${t.difficulty}">${t.difficulty}</span>
      </div>
      <div class="task-desc">${t.description}</div>
      <div class="task-meta">
        <span>Steps: ${t.expected_steps}</span>
        <span>Tools: ${t.required_tools.length}</span>
      </div>
    `;
    card.addEventListener("click", () => selectTask(t.task_id));
    $taskCards.appendChild(card);
  });
}

function selectTask(taskId) {
  if (episodeActive) return;
  selectedTaskId = taskId;
  document.querySelectorAll(".task-card").forEach((c) => {
    c.classList.toggle("selected", c.dataset.taskId === taskId);
  });
  $btnStart.disabled = false;
}

// ─── Event Listeners ──────────────────────────────────────────────
function setupEventListeners() {
  $btnStart.addEventListener("click", startEpisode);
  $btnReset.addEventListener("click", resetEpisode);

  $tabRespond.addEventListener("click", () => switchInputMode("respond"));
  $tabTool.addEventListener("click", () => switchInputMode("tool"));

  $btnSend.addEventListener("click", sendResponse);
  $btnToolSend.addEventListener("click", sendToolAction);

  $agentMessage.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendResponse();
    }
  });

  $toolSelect.addEventListener("change", renderToolParams);

  // Modal logic
  if ($btnInfoToggle && $infoModalOverlay && $btnInfoClose) {
    $btnInfoToggle.addEventListener("click", () => {
      $infoModalOverlay.style.display = "flex";
    });
    $btnInfoClose.addEventListener("click", () => {
      $infoModalOverlay.style.display = "none";
    });
    $infoModalOverlay.addEventListener("click", (e) => {
      if (e.target === $infoModalOverlay) {
        $infoModalOverlay.style.display = "none";
      }
    });
  }
}

function switchInputMode(mode) {
  $tabRespond.classList.toggle("active", mode === "respond");
  $tabTool.classList.toggle("active", mode === "tool");
  $inputRespond.style.display = mode === "respond" ? "flex" : "none";
  $inputTool.style.display = mode === "tool" ? "flex" : "none";
}

function renderToolParams() {
  const tool = $toolSelect.value;
  const params = TOOL_PARAMS[tool] || [];
  $toolParams.innerHTML = params
    .map(
      (p) => `
    <div class="tool-param-row">
      <label>${p.name}</label>
      <input type="text" id="param_${p.name}" placeholder="${p.placeholder}" />
    </div>
  `
    )
    .join("");
}

// ─── Start Episode ─────────────────────────────────────────────────
async function startEpisode() {
  if (!selectedTaskId) return;

  try {
    const res = await fetch(`${API}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: selectedTaskId }),
    });

    if (!res.ok) throw new Error("Reset failed");

    const data = await res.json();
    // Handle both flat obs and nested {observation: {...}} formats
    const obs = data.observation || data;
    currentObs = obs;

    // Reset state
    episodeActive = true;
    episodeDone = false;
    mockStepIndex = 0;
    emotionHistory = [obs.emotion_level || 0];
    cumulativeReward = 0;
    turnNumber = 0;
    maxTurns = obs.max_turns || 10;

    // Update UI
    $chatPlaceholder.style.display = "none";
    $chatArea.innerHTML = "";
    $btnStart.disabled = true;
    $btnReset.disabled = false;
    $finalScores.style.display = "none";
    $toolChips.innerHTML = '<span class="chip chip-empty">None yet</span>';
    $breakdownList.innerHTML = '<div class="breakdown-empty">Waiting for actions…</div>';

    updateTurnCounter();
    updateEmotionGauge(obs.emotion_level || 0);
    updateReward(0);
    drawEmotionChart();

    // Show customer first message
    addBubble("customer", obs.customer_message, obs.emotion_level);

    // Show input or start mock
    const mode = $runMode.value;
    if (mode === "manual") {
      $inputArea.style.display = "block";
      autoFillOrderId(obs);
    } else {
      $inputArea.style.display = "none";
      runMockEpisode();
    }

    toast(`Episode started: ${capitalize(selectedTaskId)} task`, "success");
  } catch (e) {
    toast(`Error: ${e.message}`, "error");
  }
}

function autoFillOrderId(obs) {
  if (obs && obs.order_info) {
    setTimeout(() => {
      const el = document.getElementById("param_order_id");
      if (el) el.value = obs.order_info.order_id;
    }, 100);
  }
}

// ─── Mock Episode ─────────────────────────────────────────────────
async function runMockEpisode() {
  const actions = MOCK_ACTIONS[selectedTaskId] || [];

  for (let i = 0; i < actions.length; i++) {
    if (!episodeActive || episodeDone) break;

    const typing = showTypingIndicator();
    await delay(800 + Math.random() * 600);
    typing.remove();

    const action = actions[i];
    await executeStep(action);

    if (episodeDone) break;
    await delay(400);
  }
}

// ─── Manual Send Response ─────────────────────────────────────────
async function sendResponse() {
  const msg = $agentMessage.value.trim();
  if (!msg || !episodeActive || episodeDone) return;

  $agentMessage.value = "";
  const action = { action_type: "respond", message: msg };
  await executeStep(action);
}

// ─── Manual Send Tool ─────────────────────────────────────────────
async function sendToolAction() {
  if (!episodeActive || episodeDone) return;

  const toolName = $toolSelect.value;
  const params = {};
  const paramDefs = TOOL_PARAMS[toolName] || [];
  for (const p of paramDefs) {
    const el = document.getElementById(`param_${p.name}`);
    if (el) params[p.name] = el.value.trim();
  }

  const action = {
    action_type: "call_tool",
    tool_name: toolName,
    tool_parameters: params,
  };

  await executeStep(action);
}

// ─── Execute Step ─────────────────────────────────────────────────
async function executeStep(action) {
  if (action.action_type === "respond") {
    addBubble("agent", action.message);
  } else if (action.action_type === "call_tool") {
    addBubble(
      "tool",
      `🔧 ${action.tool_name}(${JSON.stringify(action.tool_parameters)})`
    );
  }

  try {
    const res = await fetch(`${API}/step`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(action),
    });

    const data = await res.json();
    // Handle both flat and nested observation formats
    const obs = data.observation || data;
    const reward = data.reward || 0;
    const done = data.done || false;
    const info = data.info || {};

    currentObs = obs;
    turnNumber = obs.turn_number || 0;
    maxTurns = obs.max_turns || 10;
    cumulativeReward += reward;

    emotionHistory.push(obs.emotion_level || 0);
    updateEmotionGauge(obs.emotion_level || 0);
    drawEmotionChart();
    updateTurnCounter();
    updateReward(cumulativeReward);

    if (info.reward_breakdown) {
      renderBreakdown(info.reward_breakdown);
    }

    if (action.action_type === "call_tool") {
      updateToolChips(action.tool_name, obs.last_action_feedback);
    }

    if (obs.last_action_feedback) {
      addBubble("system", obs.last_action_feedback);
    }

    if (!done && obs.customer_message) {
      await delay(500);
      addBubble("customer", obs.customer_message, obs.emotion_level);
    }

    if (done) {
      episodeDone = true;
      episodeActive = false;
      $inputArea.style.display = "none";
      $btnStart.disabled = false;

      const result = info.result || info.failure || "unknown";
      const isResolved = result === "resolved";

      addDoneBanner(isResolved, result);
      await fetchFinalScores();

      toast(
        isResolved
          ? "✅ Episode resolved successfully!"
          : `❌ Episode ended: ${result}`,
        isResolved ? "success" : "error"
      );
    }
  } catch (e) {
    toast(`Step error: ${e.message}`, "error");
  }
}

// ─── Fetch & Show Final Scores ────────────────────────────────────
async function fetchFinalScores() {
  try {
    const res = await fetch(`${API}/state`);
    const state = await res.json();
    const scores = gradeLocally(state);

    $finalScores.style.display = "block";

    animateScoreRing("ringResolution", scores.resolution);
    animateScoreRing("ringToolUsage", scores.tool_usage);
    animateScoreRing("ringEmotionIQ", scores.emotional_iq);
    animateScoreRing("ringEfficiency", scores.efficiency);

    document.getElementById("finalScoreNumber").textContent =
      scores.final_score.toFixed(4);
  } catch {
    // Silently fail — scores are optional
  }
}

function gradeLocally(state) {
  const taskMeta = getTaskMeta(state.task_id);
  if (!taskMeta) {
    return { resolution: 0, tool_usage: 0, emotional_iq: 0.5, efficiency: 0, final_score: 0 };
  }

  const successConds = taskMeta.success_conditions;
  const toolsCalled = new Set(
    state.tool_calls_made
      .filter((tc) => tc.result && tc.result.success)
      .map((tc) => tc.tool)
  );
  let met = 0;
  for (const cond of successConds) {
    if (cond.startsWith("tool:")) {
      const tn = cond.split(":")[1].split(" ")[0];
      if (toolsCalled.has(tn)) met++;
    } else if (cond === "refund_processed") {
      if (toolsCalled.has("process_refund")) met++;
    } else if (cond === "escalation_done") {
      if (toolsCalled.has("escalate_to_manager")) met++;
    } else if (cond === "emotion_reduced") {
      if (
        state.emotion_history.length >= 2 &&
        state.emotion_history[state.emotion_history.length - 1] < state.emotion_history[0]
      ) met++;
    }
  }
  const resolution = successConds.length > 0 ? met / successConds.length : 1;

  const required = new Set(taskMeta.required_tools);
  const successTools = state.tool_calls_made
    .filter((tc) => tc.result && tc.result.success)
    .map((tc) => tc.tool);
  const calledRequired = new Set(successTools.filter((t) => required.has(t)));
  let toolBase = required.size > 0 ? calledRequired.size / required.size : 1;
  const unnecessary = successTools.filter((t) => !required.has(t)).length;
  const tool_usage = Math.max(0, toolBase - unnecessary * 0.1);

  let emotional_iq = 0.5;
  if (state.emotion_history.length >= 2) {
    const initial = state.emotion_history[0];
    const final = state.emotion_history[state.emotion_history.length - 1];
    if (final < initial) emotional_iq = 1.0;
    else if (Math.abs(final - initial) < 0.01) emotional_iq = 0.5;
    else emotional_iq = 0.0;
  }

  const expected = taskMeta.expected_steps;
  const maxSteps = taskMeta.max_steps;
  const actual = state.step_count;
  let efficiency = 1;
  if (actual > expected) {
    efficiency = Math.max(0, 1 - (actual - expected) / maxSteps);
  }

  const final_score =
    0.4 * resolution + 0.25 * tool_usage + 0.2 * emotional_iq + 0.15 * efficiency;

  return {
    resolution: round4(resolution),
    tool_usage: round4(tool_usage),
    emotional_iq: round4(emotional_iq),
    efficiency: round4(efficiency),
    final_score: round4(final_score),
  };
}

function getTaskMeta(taskId) {
  const tasks = {
    easy: {
      expected_steps: 3, max_steps: 10,
      required_tools: ["check_order_status"],
      success_conditions: ["tool:check_order_status called"],
      initial_emotion: 0.2,
    },
    medium: {
      expected_steps: 5, max_steps: 10,
      required_tools: ["check_order_status", "process_refund"],
      success_conditions: ["tool:check_order_status called", "tool:process_refund called", "emotion_reduced"],
      initial_emotion: 0.7,
    },
    hard: {
      expected_steps: 7, max_steps: 10,
      required_tools: ["check_order_status", "process_refund", "escalate_to_manager"],
      success_conditions: ["tool:check_order_status called", "tool:process_refund called", "tool:escalate_to_manager called", "emotion_reduced"],
      initial_emotion: 0.85,
    },
    out_of_stock: {
      expected_steps: 5, max_steps: 10,
      required_tools: ["check_order_status", "check_inventory"],
      success_conditions: ["tool:check_order_status called", "tool:check_inventory called", "emotion_reduced"],
      initial_emotion: 0.6,
    },
    subscription: {
      expected_steps: 5, max_steps: 10,
      required_tools: ["check_subscription", "apply_retention_discount"],
      success_conditions: ["tool:check_subscription called", "tool:apply_retention_discount called", "emotion_reduced"],
      initial_emotion: 0.65,
    },
  };
  return tasks[taskId] || null;
}

// ─── Reset Episode ─────────────────────────────────────────────────
function resetEpisode() {
  episodeActive = false;
  episodeDone = false;
  currentObs = null;
  emotionHistory = [];
  cumulativeReward = 0;
  turnNumber = 0;
  mockStepIndex = 0;

  $chatArea.innerHTML = "";
  $chatPlaceholder.style.display = "flex";
  $chatArea.appendChild($chatPlaceholder);
  $inputArea.style.display = "none";
  $btnStart.disabled = !selectedTaskId;
  $btnReset.disabled = true;
  $finalScores.style.display = "none";
  $toolChips.innerHTML = '<span class="chip chip-empty">None yet</span>';
  $breakdownList.innerHTML = '<div class="breakdown-empty">Waiting for actions…</div>';

  updateTurnCounter();
  updateEmotionGauge(0);
  updateReward(0);
  drawEmotionChart();

  toast("Episode reset", "info");
}

// ─── Chat Bubbles ──────────────────────────────────────────────────
function addBubble(role, content, emotion = null) {
  if ($chatPlaceholder.parentNode === $chatArea) {
    $chatPlaceholder.style.display = "none";
  }

  const div = document.createElement("div");

  if (role === "customer") {
    div.className = "chat-bubble bubble-customer";
    div.innerHTML = `
      <span class="bubble-label">👤 Customer</span>
      ${escapeHtml(content)}
      ${emotion !== null ? `<div class="bubble-emotion">😶 Emotion: ${emotion.toFixed(2)}</div>` : ""}
    `;
  } else if (role === "agent") {
    div.className = "chat-bubble bubble-agent";
    div.innerHTML = `
      <span class="bubble-label">🤖 Agent</span>
      ${escapeHtml(content)}
    `;
  } else if (role === "tool") {
    div.className = "chat-bubble bubble-tool";
    div.innerHTML = `
      <span class="bubble-label">⚙️ Tool Call</span>
      ${escapeHtml(content)}
    `;
  } else if (role === "system") {
    div.className = "chat-bubble bubble-system";
    div.textContent = content;
  }

  $chatArea.appendChild(div);
  $chatArea.scrollTop = $chatArea.scrollHeight;
}

function addDoneBanner(isResolved, reason) {
  const div = document.createElement("div");
  div.className = `episode-done-banner ${isResolved ? "resolved" : "failed"}`;
  div.textContent = isResolved
    ? "✅ Episode Resolved Successfully!"
    : `❌ Episode Failed: ${reason.replace(/_/g, " ")}`;
  $chatArea.appendChild(div);
  $chatArea.scrollTop = $chatArea.scrollHeight;
}

function showTypingIndicator() {
  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = "<span></span><span></span><span></span>";
  $chatArea.appendChild(div);
  $chatArea.scrollTop = $chatArea.scrollHeight;
  return div;
}

// ─── Metric Updates ───────────────────────────────────────────────
function updateTurnCounter() {
  $turnCount.textContent = turnNumber;
  $maxTurns.textContent = maxTurns;
}

function updateEmotionGauge(emotion) {
  const total = 157;
  const offset = total - emotion * total;
  $emotionArc.style.strokeDashoffset = offset;
  $emotionValue.textContent = emotion.toFixed(2);
}

function updateReward(reward) {
  $rewardValue.textContent = reward.toFixed(4);
  $rewardValue.className =
    "reward-value " + (reward > 0 ? "positive" : reward < 0 ? "negative" : "neutral");

  const pct = Math.max(0, Math.min(100, 50 + (reward / 2) * 50));
  $rewardBar.style.width = `${pct}%`;

  if (reward > 0) {
    $rewardBar.style.background = "var(--gradient-cool)";
  } else if (reward < 0) {
    $rewardBar.style.background = "var(--gradient-warm)";
  } else {
    $rewardBar.style.background = "var(--gradient-primary)";
  }
}

function updateToolChips(toolName, feedback) {
  const empty = $toolChips.querySelector(".chip-empty");
  if (empty) empty.remove();

  const chip = document.createElement("span");
  const isSuccess = feedback && feedback.includes("successfully");
  chip.className = `chip ${isSuccess ? "chip-success" : "chip-error"}`;
  chip.textContent = `${isSuccess ? "✓" : "✗"} ${toolName}`;
  $toolChips.appendChild(chip);
}

function renderBreakdown(breakdown) {
  $breakdownList.innerHTML = "";
  for (const [key, val] of Object.entries(breakdown)) {
    const item = document.createElement("div");
    item.className = "breakdown-item";
    const cls = val > 0 ? "pos" : val < 0 ? "neg" : "";
    item.innerHTML = `
      <span class="bd-label">${key.replace(/_/g, " ")}</span>
      <span class="bd-value ${cls}">${val > 0 ? "+" : ""}${val.toFixed(4)}</span>
    `;
    $breakdownList.appendChild(item);
  }
}

// ─── Emotion Chart ─────────────────────────────────────────────────
function drawEmotionChart() {
  const canvas = document.getElementById("emotionChart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  if (emotionHistory.length < 2) {
    ctx.fillStyle = "rgba(255,255,255,0.05)";
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "rgba(255,255,255,0.15)";
    ctx.font = "11px Inter";
    ctx.textAlign = "center";
    ctx.fillText("Awaiting data…", w / 2, h / 2 + 4);
    return;
  }

  const data = emotionHistory;
  const maxPoints = 15;
  const points = data.length > maxPoints ? data.slice(-maxPoints) : data;
  const stepX = w / (points.length - 1 || 1);
  const pad = 8;
  const usableH = h - pad * 2;

  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(99, 102, 241, 0.25)");
  grad.addColorStop(1, "rgba(99, 102, 241, 0.02)");

  ctx.beginPath();
  ctx.moveTo(0, h);
  for (let i = 0; i < points.length; i++) {
    const x = i * stepX;
    const y = pad + (1 - points[i]) * usableH;
    if (i === 0) ctx.lineTo(x, y);
    else {
      const prevX = (i - 1) * stepX;
      const prevY = pad + (1 - points[i - 1]) * usableH;
      const cpx = (prevX + x) / 2;
      ctx.bezierCurveTo(cpx, prevY, cpx, y, x, y);
    }
  }
  ctx.lineTo((points.length - 1) * stepX, h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  for (let i = 0; i < points.length; i++) {
    const x = i * stepX;
    const y = pad + (1 - points[i]) * usableH;
    if (i === 0) ctx.moveTo(x, y);
    else {
      const prevX = (i - 1) * stepX;
      const prevY = pad + (1 - points[i - 1]) * usableH;
      const cpx = (prevX + x) / 2;
      ctx.bezierCurveTo(cpx, prevY, cpx, y, x, y);
    }
  }
  ctx.strokeStyle = "#6366f1";
  ctx.lineWidth = 2;
  ctx.stroke();

  for (let i = 0; i < points.length; i++) {
    const x = i * stepX;
    const y = pad + (1 - points[i]) * usableH;
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    const emotion = points[i];
    ctx.fillStyle =
      emotion < 0.3 ? "#22c55e"
      : emotion < 0.6 ? "#eab308"
      : emotion < 0.8 ? "#f97316"
      : "#ef4444";
    ctx.fill();
    ctx.strokeStyle = "#0a0a1a";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

// ─── Score Ring Animation ─────────────────────────────────────────
function animateScoreRing(id, score) {
  const ring = document.getElementById(id);
  const arc = ring.querySelector(".score-arc");
  const val = ring.querySelector(".score-val");
  const circumference = 113;

  const target = circumference - score * circumference;
  arc.style.strokeDashoffset = target;
  val.textContent = `${Math.round(score * 100)}%`;
}

// ─── Toast Notifications ──────────────────────────────────────────
function toast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  const icons = { success: "✅", error: "❌", info: "ℹ️" };
  el.innerHTML = `<span>${icons[type] || ""}</span><span>${escapeHtml(message)}</span>`;
  $toastContainer.appendChild(el);

  setTimeout(() => {
    el.classList.add("toast-out");
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// ─── Utilities ────────────────────────────────────────────────────
function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function round4(n) {
  return Math.round(n * 10000) / 10000;
}
