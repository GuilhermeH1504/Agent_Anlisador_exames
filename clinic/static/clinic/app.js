const state = {
  threadId: localStorage.getItem("aidoctorThreadId") || makeThreadId(),
  busy: false
};

localStorage.setItem("aidoctorThreadId", state.threadId);

const $ = (selector) => document.querySelector(selector);

function makeThreadId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return "web-" + Date.now().toString(36);
}

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const [key, ...value] = cookie.trim().split("=");
    if (key === name) return decodeURIComponent(value.join("="));
  }
  return "";
}

function escapeHtml(text) {
  return String(text || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}

async function requestJson(url, options = {}) {
  const headers = options.headers || {};
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET") {
    headers["X-CSRFToken"] = getCookie("csrftoken");
  }

  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Falha na requisicao.");
  }
  return data;
}

function appendMessage(role, agent, content) {
  const message = document.createElement("article");
  message.className = "message " + role;
  message.innerHTML = `<small>${escapeHtml(agent)}</small>${escapeHtml(content)}`;
  $("#messages").appendChild(message);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return message;
}

function setBusy(isBusy) {
  state.busy = isBusy;
  $("#sendButton").disabled = isBusy;
  $("#chatInput").disabled = isBusy;
}

async function sendPrompt(prompt) {
  const text = prompt.trim();
  if (!text || state.busy) return;

  appendMessage("user", "Paciente", text);
  $("#chatInput").value = "";
  setBusy(true);
  const loading = appendMessage("assistant", "AIDoctor", "Processando...");

  try {
    const data = await requestJson("/api/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, thread_id: state.threadId })
    });
    loading.remove();
    data.messages.forEach((msg) => appendMessage("assistant", msg.agent, msg.content));
  } catch (error) {
    loading.remove();
    appendMessage("error", "Erro", error.message);
  } finally {
    setBusy(false);
    refreshStatus();
  }
}

async function refreshStatus() {
  const data = await requestJson("/api/status/");
  $("#apiStatus").textContent = data.api_configured ? "API ativa" : "API pendente";
  $("#apiStatus").className = "pill " + (data.api_configured ? "good" : "warn");
  $("#examStatus").textContent = `${data.exams.length} exames`;
  $("#examCount").textContent = data.exams.length;
  $("#patientCount").textContent = data.patients.length;
  $("#examFolder").innerHTML = `<strong>${escapeHtml(data.exams_folder)}</strong>`;

  $("#apiNotice").classList.toggle("hidden", data.api_configured);
  $("#apiNotice").textContent = data.api_configured
    ? ""
    : "Configure GOOGLE_API_KEY ou GEMINI_API_KEY no arquivo .env para conversar com a IA.";

  renderList("#examList", data.exams, (exam) => `
    <strong>${escapeHtml(exam.name)}</strong>
    <span>${formatBytes(exam.size)}</span>
  `);

  renderList("#patientList", data.patients, (patient) => `
    <strong>${escapeHtml(patient.patient_name)}</strong>
    <span>${patient.age} anos | ${escapeHtml(patient.telephone)}</span>
  `);
}

function renderList(selector, items, render) {
  const list = $(selector);
  list.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "list-item";
    empty.innerHTML = "<span>Nenhum registro.</span>";
    list.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "list-item";
    li.innerHTML = render(item);
    list.appendChild(li);
  });
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, index);
  return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
}

$("#chatForm").addEventListener("submit", (event) => {
  event.preventDefault();
  sendPrompt($("#chatInput").value);
});

$("#patientForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  try {
    const patient = await requestJson("/api/patients/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(form.entries()))
    });
    appendMessage("assistant", "Sistema", `Paciente cadastrado: ${patient.patient.patient_name}`);
    formElement.reset();
    refreshStatus();
  } catch (error) {
    appendMessage("error", "Erro", error.message);
  }
});

$("#examForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  try {
    const data = await requestJson("/api/exams/", {
      method: "POST",
      body: form
    });
    appendMessage("assistant", "Sistema", `${data.saved.length} PDF(s) enviado(s).`);
    formElement.reset();
    refreshStatus();
  } catch (error) {
    appendMessage("error", "Erro", error.message);
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => sendPrompt(button.dataset.prompt));
});

$("#refreshButton").addEventListener("click", refreshStatus);
$("#clearChat").addEventListener("click", () => {
  state.threadId = makeThreadId();
  localStorage.setItem("aidoctorThreadId", state.threadId);
  $("#messages").innerHTML = "";
});

appendMessage("assistant", "Clara", "Ola, sou a Clara. Pode iniciar o atendimento.");
refreshStatus().catch((error) => appendMessage("error", "Erro", error.message));
