/**
 * सुविधा वाणी (SuvidhaVani) - Client Application Controller
 * Handles Multilingual Web Speech API (STT/TTS), View Routing,
 * Real-time Slot Inspection, Explainability Modals, and the SIH Judge Suite.
 */

// Application Global State
const state = {
  sessionId: "session_" + Math.random().toString(36).substring(2, 9),
  language: "hi", // default to Hindi
  voiceOutputEnabled: true,
  currentRole: "citizen",
  activeView: "voice",
  currentProfile: {},
  evaluations: [],
  catalogSchemes: [],
  isListening: false,
  recognition: null,
  turnCount: 0
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  initSpeech();
  loadCatalogData();
  resetConversation();
});

// ==========================================
// SPEECH RECOGNITION (STT) & SYNTHESIS (TTS)
// ==========================================
function initSpeech() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    state.recognition = new SpeechRecognition();
    state.recognition.continuous = false;
    state.recognition.interimResults = false;
    state.recognition.lang = state.language === "hi" ? "hi-IN" : "en-IN";

    state.recognition.onstart = () => {
      state.isListening = true;
      updateMicUI(true);
      setWaveformActive(true);
      document.getElementById("voice-indicator-status").innerText = "Listening... बोलिए...";
    };

    state.recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      document.getElementById("chat-text-input").value = transcript;
      submitUserMessage(transcript);
    };

    state.recognition.onerror = (event) => {
      console.warn("Speech recognition error:", event.error);
      state.isListening = false;
      updateMicUI(false);
      setWaveformActive(false);
      document.getElementById("voice-indicator-status").innerText = "Mic Ready • Click Mic or Type Below";
    };

    state.recognition.onend = () => {
      state.isListening = false;
      updateMicUI(false);
      setWaveformActive(false);
    };
  } else {
    console.info("Web Speech API not supported in this browser. Fallback to text input.");
  }
}

function toggleVoiceInput() {
  if (!state.recognition) {
    alert("Web Speech API is not supported in this browser. Please type your message in the text input box below.");
    return;
  }
  if (state.isListening) {
    state.recognition.stop();
  } else {
    state.recognition.lang = state.language === "hi" ? "hi-IN" : "en-IN";
    try {
      state.recognition.start();
    } catch (e) {
      console.warn("Recognition already active", e);
    }
  }
}

function updateMicUI(listening) {
  const micBtn = document.getElementById("mic-btn");
  if (listening) {
    micBtn.classList.add("listening");
  } else {
    micBtn.classList.remove("listening");
  }
}

function setWaveformActive(active) {
  const bars = document.querySelectorAll("#waveform-visualizer .wave-bar");
  bars.forEach(b => {
    if (active) b.classList.add("animating");
    else b.classList.remove("animating");
  });
}

function toggleAudioOutput() {
  state.voiceOutputEnabled = !state.voiceOutputEnabled;
  const btn = document.getElementById("voice-toggle-btn");
  const icon = document.getElementById("voice-icon");
  const label = document.getElementById("voice-label");

  if (state.voiceOutputEnabled) {
    btn.classList.add("active");
    icon.innerText = "🔊";
    label.innerText = "Voice ON";
  } else {
    btn.classList.remove("active");
    icon.innerText = "🔇";
    label.innerText = "Voice Muted";
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }
}

function playSpeech(text, lang) {
  if (!state.voiceOutputEnabled || !window.speechSynthesis) return;

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang === "hi" ? "hi-IN" : "en-IN";
  utterance.rate = 0.95; // Clear and polite pacing for citizens

  // Try to pick an authentic Indian voice
  const voices = window.speechSynthesis.getVoices();
  const indianVoice = voices.find(v => v.lang.includes("IN") || v.name.includes("India") || (lang === "hi" && v.lang.startsWith("hi")));
  if (indianVoice) {
    utterance.voice = indianVoice;
  }

  utterance.onstart = () => {
    setWaveformActive(true);
    document.getElementById("voice-indicator-status").innerText = "Agent Speaking • सुविधा वाणी बोल रही है...";
  };

  utterance.onend = () => {
    setWaveformActive(false);
    document.getElementById("voice-indicator-status").innerText = "Mic Ready • Click Mic or Type Below";
  };

  window.speechSynthesis.speak(utterance);
}

// ==========================================
// VIEW ROUTING
// ==========================================
function switchView(viewName) {
  state.activeView = viewName;

  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.getAttribute("data-view") === viewName) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  document.querySelectorAll(".app-view").forEach(view => {
    if (view.id === `view-${viewName}`) {
      view.classList.add("active-view");
    } else {
      view.classList.remove("active-view");
    }
  });

  // View specific refreshes
  if (viewName === "dashboard") refreshDashboard();
  if (viewName === "catalog") renderCatalog(state.catalogSchemes);
  if (viewName === "compare") populateCompareDropdowns();
  if (viewName === "checklist") renderDocumentChecklist();
}

function changeLanguage(lang) {
  state.language = lang;
  if (state.recognition) {
    state.recognition.lang = lang === "hi" ? "hi-IN" : "en-IN";
  }
  // Re-render UI with language preferences if needed
  console.log("Language switched to:", lang);
}

// ==========================================
// VOICE ASSISTANT CHAT LOGIC
// ==========================================
function submitUserMessage(optionalText) {
  const inputEl = document.getElementById("chat-text-input");
  const text = (optionalText || inputEl.value || "").trim();
  if (!text) return;

  inputEl.value = "";
  appendMessage("user", text);

  // Call API
  document.getElementById("voice-indicator-status").innerText = "Analyzing rules & profile...";
  
  fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: text,
      session_id: state.sessionId,
      language: state.language
    })
  })
  .then(res => res.json())
  .then(data => {
    handleAgentResponse(data);
  })
  .catch(err => {
    console.error("Chat turn error:", err);
    appendMessage("agent", "माफ कीजिये, सर्वर से संपर्क नहीं हो पाया। कृपया पुनः प्रयास करें। (Connection error, please try again.)");
    document.getElementById("voice-indicator-status").innerText = "Ready • Click Mic or Type Below";
  });
}

function handleInputKey(event) {
  if (event.key === "Enter") {
    submitUserMessage();
  }
}

function sendQuickPrompt(promptText) {
  document.getElementById("chat-text-input").value = promptText;
  submitUserMessage(promptText);
}

function handleAgentResponse(data) {
  state.turnCount = data.questions_asked_count || 0;
  state.currentProfile = data.caller_profile || {};
  state.evaluations = data.schemes_evaluation || [];

  const spoken = data.spoken_text || data.agent_message_hi || data.agent_message_en;
  
  // Create badges for message tags
  const tags = [];
  if (data.contradiction) {
    tags.push({ type: "tag-contradiction", label: `⚠️ Contradiction Detected: ${data.contradiction.slot}` });
  }
  if (data.disambiguation) {
    tags.push({ type: "tag-vague", label: `💡 Vague Answer Clarification: ${data.disambiguation.slot}` });
  }
  if (data.slots_extracted_this_turn && Object.keys(data.slots_extracted_this_turn).length > 0) {
    const slotsStr = Object.entries(data.slots_extracted_this_turn).map(([k, v]) => `${k}=${v}`).join(", ");
    tags.push({ type: "tag-slots", label: `🏷️ Extracted: ${slotsStr}` });
  }

  appendMessage("agent", spoken, tags);
  playSpeech(spoken, data.current_language || state.language);

  // Update Co-pilot Sidebar
  updateSlotInspector(data.caller_profile);
  updateSidebarMatches(data.schemes_evaluation);
}

function appendMessage(role, text, tags = []) {
  const container = document.getElementById("chat-messages");
  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.innerText = role === "agent" ? "🤖" : "👤";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const textNode = document.createElement("div");
  textNode.innerText = text;
  bubble.appendChild(textNode);

  if (tags && tags.length > 0) {
    const tagsContainer = document.createElement("div");
    tagsContainer.style.display = "flex";
    tagsContainer.style.flexWrap = "wrap";
    tagsContainer.style.gap = "4px";
    tags.forEach(t => {
      const span = document.createElement("span");
      span.className = `alert-tag ${t.type}`;
      span.innerText = t.label;
      tagsContainer.appendChild(span);
    });
    bubble.appendChild(tagsContainer);
  }

  const timeDiv = document.createElement("div");
  timeDiv.className = "msg-timestamp";
  const now = new Date();
  timeDiv.innerText = `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}`;
  bubble.appendChild(timeDiv);

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function resetConversation() {
  fetch("/api/chat/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId, language: state.language })
  })
  .then(res => res.json())
  .then(data => {
    const container = document.getElementById("chat-messages");
    container.innerHTML = "";
    appendMessage("agent", data.greeting_message || "नमस्ते! मैं सुविधा वाणी हूँ, आपका सरकारी योजना सहायक। आप क्या काम करते हैं और क्या सहायता चाहते हैं?");
    playSpeech(data.greeting_message, state.language);
    updateSlotInspector({});
    updateSidebarMatches([]);
    document.getElementById("slot-turn-counter").innerText = "Turns: 0";
  });
}

// ==========================================
// SLOT INSPECTOR & SIDEBAR MATCHES
// ==========================================
function updateSlotInspector(profile) {
  const p = profile || {};
  document.getElementById("slot-age").innerText = p.age ? `${p.age} yrs` : "--";
  document.getElementById("slot-occupation").innerText = p.occupation ? p.occupation : "--";
  document.getElementById("slot-income").innerText = p.annual_income ? `₹${p.annual_income.toLocaleString('en-IN')}` : "--";
  document.getElementById("slot-land").innerText = p.has_land ? `${p.land_ha || 1} ha` : (p.has_land === false ? "Landless" : "--");
  document.getElementById("slot-area").innerText = p.area_type || "--";
  document.getElementById("slot-house").innerText = p.house_type || "--";
  document.getElementById("slot-bpl").innerText = p.bpl_status ? "BPL (Yes)" : (p.bpl_status === false ? "No" : "--");
  document.getElementById("slot-tax").innerText = p.is_tax_payer ? "Taxpayer (Yes)" : (p.is_tax_payer === false ? "Non-Taxpayer" : "--");

  document.querySelectorAll(".slot-val").forEach(el => {
    if (el.innerText !== "--") el.classList.remove("empty");
    else el.classList.add("empty");
  });
}

function updateSidebarMatches(evaluations) {
  const container = document.getElementById("sidebar-matches-list");
  container.innerHTML = "";

  if (!evaluations || evaluations.length === 0) {
    container.innerHTML = `<div style="font-size:12px; color:#64748B; text-align:center; padding:20px 0;">No schemes evaluated yet.</div>`;
    document.getElementById("eligible-badge-count").innerText = "0 Eligible";
    return;
  }

  const eligibleCount = evaluations.filter(e => e.status === "ELIGIBLE").length;
  document.getElementById("eligible-badge-count").innerText = `${eligibleCount} Eligible`;

  evaluations.slice(0, 6).forEach(sch => {
    const card = document.createElement("div");
    card.className = `match-card ${sch.status.toLowerCase()}`;

    const titleLang = state.language === "hi" ? sch.name_hi : sch.name_en;
    const benefitsLang = state.language === "hi" ? sch.benefits_hi : sch.benefits_en;

    card.innerHTML = `
      <div class="match-card-header">
        <span class="match-name">${titleLang}</span>
        <span class="status-badge ${sch.status.toLowerCase()}">${sch.status.replace('_', ' ')}</span>
      </div>
      <div class="match-benefit">${benefitsLang.substring(0, 85)}...</div>
      <div class="match-actions">
        <button class="btn-explain" onclick="openExplainModal('${sch.scheme_id}')">🔍 Explain Reason</button>
        <button class="btn-explain" onclick="saveSchemeBookmark('${sch.scheme_id}')">📌 Bookmark</button>
      </div>
    `;
    container.appendChild(card);
  });
}

// ==========================================
// EXPLAINABILITY MODAL
// ==========================================
function openExplainModal(schemeId) {
  const schemeEval = state.evaluations.find(e => e.scheme_id === schemeId);
  const rawScheme = state.catalogSchemes.find(s => s.id === schemeId);
  const modal = document.getElementById("explain-modal");

  if (!schemeEval && !rawScheme) return;

  const title = state.language === "hi" ? (schemeEval?.name_hi || rawScheme?.name_hi) : (schemeEval?.name_en || rawScheme?.name_en);
  const benefits = state.language === "hi" ? (schemeEval?.benefits_hi || rawScheme?.benefits_hi) : (schemeEval?.benefits_en || rawScheme?.benefits_en);
  const status = schemeEval ? schemeEval.status : "EVALUATE_PROFILE";

  document.getElementById("modal-scheme-title").innerText = title;
  const badge = document.getElementById("modal-scheme-badge");
  badge.className = `status-badge ${status.toLowerCase()}`;
  badge.innerText = status.replace('_', ' ');

  document.getElementById("modal-benefits-box").innerHTML = `<strong>✨ Entitlement Benefit:</strong> ${benefits}`;

  const tbody = document.getElementById("modal-rules-tbody");
  tbody.innerHTML = "";

  if (schemeEval && schemeEval.criteria_breakdown) {
    schemeEval.criteria_breakdown.forEach(rule => {
      const tr = document.createElement("tr");
      const ruleLabel = state.language === "hi" ? rule.criterion_label_hi : rule.criterion_label_en;
      const explanation = state.language === "hi" ? rule.explanation_hi : rule.explanation_en;

      tr.innerHTML = `
        <td><strong>${ruleLabel}</strong></td>
        <td>${rule.required_value || '--'}</td>
        <td>${rule.actual_value !== null ? rule.actual_value : '<em style="color:#94A3B8;">Pending verification</em>'}</td>
        <td>
          <span class="rule-status-pill ${rule.status}">${rule.status}</span>
          <div style="font-size:11px; color:#475569; margin-top:2px;">${explanation}</div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#64748B;">Use the Voice Assistant or Profile Form to run deterministic rule matching.</td></tr>`;
  }

  const appSteps = state.language === "hi" ? (schemeEval?.application_steps_hi || rawScheme?.application_steps_hi) : (schemeEval?.application_steps_en || rawScheme?.application_steps_en);
  document.getElementById("modal-next-steps").innerText = appSteps || "Apply directly via the official portal or your local CSC.";
  document.getElementById("modal-portal-link").href = schemeEval?.portal_url || rawScheme?.portal_url || "#";

  modal.classList.add("active");
}

function closeExplainModal() {
  document.getElementById("explain-modal").classList.remove("active");
}

// ==========================================
// SCHEMES CATALOG & BROWSE
// ==========================================
function loadCatalogData() {
  fetch("/api/schemes")
    .then(res => res.json())
    .then(data => {
      state.catalogSchemes = data.schemes || data;
      renderCatalog(state.catalogSchemes);
    });
}

function renderCatalog(schemes) {
  const container = document.getElementById("catalog-grid");
  if (!container) return;
  container.innerHTML = "";

  schemes.forEach(s => {
    const card = document.createElement("div");
    card.className = "scheme-card";

    const title = state.language === "hi" ? s.name_hi : s.name_en;
    const brief = state.language === "hi" ? s.brief_hi : s.brief_en;
    const benefits = state.language === "hi" ? s.benefits_hi : s.benefits_en;

    card.innerHTML = `
      <div>
        <div class="scheme-tags-bar">
          <span class="scheme-tag" style="background:#EFF6FF; color:#1E40AF;">${s.level}</span>
          <span class="scheme-tag">${s.category}</span>
          <span class="scheme-tag" style="background:#DCFCE7; color:#166534;">Verified: ${s.verified_date || '2024-11'}</span>
        </div>
        <h3>${title}</h3>
        <p class="scheme-brief">${brief}</p>
        <div class="scheme-benefits-box">
          <strong>Key Benefit:</strong> ${benefits.substring(0, 110)}...
        </div>
      </div>
      <div class="scheme-card-footer">
        <a href="${s.portal_url}" target="_blank" style="font-size:12px; color:#1E3A8A; font-weight:700; text-decoration:none;">Portal ↗</a>
        <div style="display:flex; gap:6px;">
          <button class="btn-secondary" style="font-size:11px; padding:4px 8px;" onclick="openExplainModal('${s.id}')">View Rules</button>
          <button class="btn-primary" style="font-size:11px; padding:4px 8px;" onclick="quickTestSchemeInVoice('${s.id}')">Test in Voice</button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function filterByCategory(category) {
  if (category === "all") {
    renderCatalog(state.catalogSchemes);
  } else {
    const filtered = state.catalogSchemes.filter(s => s.category.toLowerCase().includes(category.toLowerCase()));
    renderCatalog(filtered);
  }
}

function filterCatalog() {
  const q = document.getElementById("catalog-search-input").value.toLowerCase();
  const filtered = state.catalogSchemes.filter(s =>
    s.name_en.toLowerCase().includes(q) ||
    s.name_hi.toLowerCase().includes(q) ||
    s.brief_en.toLowerCase().includes(q) ||
    s.category.toLowerCase().includes(q)
  );
  renderCatalog(filtered);
}

function quickTestSchemeInVoice(schemeId) {
  switchView("voice");
  sendQuickPrompt(`मुझे ${schemeId} योजना के बारे में बताएं और क्या मैं इसके लिए पात्र हूँ?`);
}

// ==========================================
// SCHEME COMPARISON TOOL
// ==========================================
function populateCompareDropdowns() {
  const s1 = document.getElementById("compare-s1");
  const s2 = document.getElementById("compare-s2");
  const s3 = document.getElementById("compare-s3");
  if (!s1 || !s2) return;

  const buildOptions = (selectedId) => {
    return state.catalogSchemes.map(s => `
      <option value="${s.id}" ${s.id === selectedId ? 'selected' : ''}>
        ${s.code || s.id}: ${s.name_en.substring(0, 25)}...
      </option>
    `).join("");
  };

  s1.innerHTML = buildOptions("pm_kisan");
  s2.innerHTML = buildOptions("pmjay");
  s3.innerHTML = `<option value="">-- None --</option>` + buildOptions("pmay_g");
}

function runComparison() {
  const id1 = document.getElementById("compare-s1").value;
  const id2 = document.getElementById("compare-s2").value;
  const id3 = document.getElementById("compare-s3").value;

  const ids = [id1, id2, id3].filter(Boolean);
  if (ids.length < 2) return;

  fetch("/api/schemes/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheme_ids: ids })
  })
  .then(res => res.json())
  .then(data => {
    renderComparisonTable(data);
  });
}

function renderComparisonTable(matrix) {
  const container = document.getElementById("comparison-results-container");
  if (matrix.error) {
    container.innerHTML = `<p style="color:#B91C1C;">${matrix.error}</p>`;
    return;
  }

  let html = `
    <table class="rules-breakdown-table">
      <thead>
        <tr>
          <th style="width:20%;">Comparison Dimension</th>
          ${matrix.schemes.map(s => `<th>${s.name_en}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
  `;

  matrix.dimensions.forEach(dim => {
    html += `
      <tr>
        <td><strong>${dim.label_en}</strong></td>
        ${matrix.schemes.map(s => {
          const valObj = matrix.values[s.id][dim.key];
          const val = state.language === "hi" ? valObj.hi : valObj.en;
          return `<td>${val}</td>`;
        }).join("")}
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

// ==========================================
// DOCUMENT CHECKLIST
// ==========================================
function renderDocumentChecklist() {
  const eligibleIds = state.evaluations.filter(e => e.status === "ELIGIBLE" || e.status === "LIKELY_ELIGIBLE").map(e => e.scheme_id);
  const targetIds = eligibleIds.length > 0 ? eligibleIds : ["pm_kisan", "pmjay", "pmay_g"];

  fetch("/api/schemes/checklist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheme_ids: targetIds })
  })
  .then(res => res.json())
  .then(data => {
    const container = document.getElementById("checklist-items-container");
    container.innerHTML = "";

    data.documents.forEach((doc, idx) => {
      const title = state.language === "hi" ? doc.title_hi : doc.title_en;
      const category = state.language === "hi" ? doc.category_hi : doc.category_en;
      const authority = state.language === "hi" ? doc.issuing_authority_hi : doc.issuing_authority_en;
      const tip = state.language === "hi" ? doc.pro_tip_hi : doc.pro_tip_en;

      const item = document.createElement("div");
      item.style.background = "white";
      item.style.border = "1px solid #CBD5E1";
      item.style.borderRadius = "8px";
      item.style.padding = "14px 18px";
      item.style.display = "flex";
      item.style.justifyContent = "space-between";
      item.style.alignItems = "center";

      item.innerHTML = `
        <div style="display:flex; align-items:center; gap:12px;">
          <input type="checkbox" id="chk-${idx}" style="width:18px; height:18px; cursor:pointer;">
          <div>
            <div style="font-weight:700; font-size:14px; color:#1E3A8A;">${title}</div>
            <div style="font-size:12px; color:#64748B;">Category: <strong>${category}</strong> • Authority: ${authority}</div>
            <div style="font-size:11px; color:#059669; margin-top:2px;">💡 <em>${tip}</em></div>
          </div>
        </div>
        <span class="scheme-tag" style="background:#EFF6FF; color:#1E40AF;">For: ${doc.needed_for_schemes.join(", ")}</span>
      `;
      container.appendChild(item);
    });
  });
}

// ==========================================
// CITIZEN DASHBOARD
// ==========================================
function refreshDashboard() {
  fetch("/api/eligibility/dashboard?user_id=1")
    .then(res => res.json())
    .then(data => {
      document.getElementById("dash-total-evaluated").innerText = data.stats.total_evaluated;
      document.getElementById("dash-eligible-count").innerText = data.stats.eligible_count;
      document.getElementById("dash-likely-count").innerText = data.stats.likely_count;
      document.getElementById("dash-ineligible-count").innerText = data.stats.ineligible_count;
      document.getElementById("dash-saved-count").innerText = data.stats.saved_count;

      const recContainer = document.getElementById("dash-recommended-container");
      recContainer.innerHTML = "";
      const recs = data.eligible_schemes.concat(data.likely_schemes);
      if (recs.length === 0) {
        recContainer.innerHTML = `<p style="color:#64748B; font-size:13px;">No schemes matched yet. Talk to the Voice Assistant or complete the Profile Form.</p>`;
      } else {
        recs.forEach(s => {
          const div = document.createElement("div");
          div.className = "scheme-card";
          div.innerHTML = `
            <h3>${s.name_en}</h3>
            <p class="scheme-brief">${s.benefits_en.substring(0, 110)}...</p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
              <span class="status-badge ${s.status.toLowerCase()}">${s.status}</span>
              <button class="btn-primary" style="font-size:11px; padding:4px 8px;" onclick="openExplainModal('${s.scheme_id}')">Explain Reason</button>
            </div>
          `;
          recContainer.appendChild(div);
        });
      }
    });
}

function saveSchemeBookmark(schemeId) {
  fetch("/api/eligibility/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: 1, scheme_id: schemeId, status: "interested" })
  })
  .then(res => res.json())
  .then(data => {
    alert("Scheme successfully bookmarked to your Citizen Dashboard!");
    refreshDashboard();
  });
}

// ==========================================
// CITIZEN PROFILE FORM
// ==========================================
function handleManualProfileSubmit(event) {
  event.preventDefault();
  const req = {
    age: parseInt(document.getElementById("form-age").value) || null,
    gender: document.getElementById("form-gender").value || null,
    occupation: document.getElementById("form-occupation").value || null,
    annual_income: parseFloat(document.getElementById("form-income").value) || null,
    area_type: document.getElementById("form-area").value || null,
    house_type: document.getElementById("form-house").value || null,
    land_ha: parseFloat(document.getElementById("form-land").value) || null,
    has_land: parseFloat(document.getElementById("form-land").value) > 0,
    bpl_status: document.getElementById("form-bpl").value === "true" ? true : (document.getElementById("form-bpl").value === "false" ? false : null),
    is_tax_payer: document.getElementById("form-tax").value === "true",
    has_girl_child_under_10: document.getElementById("form-girl-child").value === "true" ? true : null
  };

  fetch("/api/eligibility/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req)
  })
  .then(res => res.json())
  .then(data => {
    state.evaluations = data.evaluations;
    state.currentProfile = data.profile;
    updateSlotInspector(data.profile);
    updateSidebarMatches(data.evaluations);
    switchView("dashboard");
  });
}

function resetProfileForm() {
  document.getElementById("profile-manual-form").reset();
}

// ==========================================
// SIH JUDGE BENCHMARK SUITE
// ==========================================
function loadScenarioToVoice(scenarioId) {
  switchView("voice");
  resetConversation();

  const scenarioPrompts = {
    "sih_scenario_1_eligible": "नमस्ते, मैं 45 वर्ष का किसान हूँ, गाँव में 1 हेक्टेयर ज़मीन पर खेती करता हूँ और मेरी सालाना आय 80 हज़ार रुपये है, मैं कोई टैक्स नहीं भरता।",
    "sih_scenario_2_ineligible": "Hello, I am 35 years old, earning 14 Lakh per year and paying regular income tax. I want to apply for BPL housing and free government ration schemes.",
    "sih_scenario_3_incomplete": "नमस्ते, मैं गाँव में रहता हूँ, उम्र 42 साल है, लेकिन मुझे अपनी सालाना कमाई का पक्का नहीं पता, बस थोड़ा बहुत कमा लेते हैं।",
    "sih_scenario_4_contradictory": "Mera naam Sunil hai aur meri umar 24 saal hai. Mujhe 60 saal wali vriddhavastha pension chahiye.",
    "sih_scenario_5_multilingual": "प्रणाम, मैं एक ग्रामीण महिला हूँ, उम्र 28 वर्ष है और मेरे घर में गैस सिलेंडर नहीं है, हम चूल्हे पर खाना बनाते हैं।"
  };

  const text = scenarioPrompts[scenarioId];
  if (text) {
    setTimeout(() => {
      sendQuickPrompt(text);
    }, 400);
  }
}

function runAllSIHBenchmarks() {
  const container = document.getElementById("benchmark-scorecard-area");
  container.innerHTML = `<div style="text-align:center; padding:20px; color:#7E22CE; font-weight:700;">Running all 5 Mandatory SIH Benchmark Scenarios against rules engine...</div>`;

  fetch("/api/benchmark/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: "all" })
  })
  .then(res => res.json())
  .then(data => {
    const sc = data.scorecard;
    let html = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <h3 style="font-size:18px; font-weight:800; color:#1E3A8A;">🏅 SIH Evaluation Official Scorecard</h3>
        <span class="status-badge eligible" style="font-size:12px; padding:4px 10px;">${sc.sih_benchmarking_status}</span>
      </div>

      <div class="dashboard-metrics-grid" style="margin-bottom:20px;">
        <div class="metric-card eligible">
          <div class="metric-title">Eligibility Accuracy</div>
          <div class="metric-value">${sc.accuracy_percentage}</div>
        </div>
        <div class="metric-card" style="border-left:4px solid #1E40AF;">
          <div class="metric-title">Avg Questions Asked</div>
          <div class="metric-value">${sc.average_questions_asked}</div>
        </div>
        <div class="metric-card eligible">
          <div class="metric-title">Contradiction Caught</div>
          <div class="metric-value">${sc.contradiction_handling_rate}</div>
        </div>
        <div class="metric-card eligible">
          <div class="metric-title">Vague Disambiguation</div>
          <div class="metric-value">${sc.vague_disambiguation_rate}</div>
        </div>
      </div>

      <table class="rules-breakdown-table">
        <thead>
          <tr>
            <th>Scenario Tested</th>
            <th>Turns</th>
            <th>Questions</th>
            <th>Latency</th>
            <th>Result & Reasoning Verification</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.results.forEach(r => {
      html += `
        <tr>
          <td><strong>${r.title}</strong></td>
          <td>${r.turns_taken}</td>
          <td>${r.questions_asked}</td>
          <td>${r.latency_ms} ms</td>
          <td>
            <span class="rule-status-pill ${r.passed ? 'PASSED' : 'FAILED'}">${r.passed ? 'PASSED' : 'FAILED'}</span>
            <div style="font-size:11px; color:#334155; margin-top:2px;">${r.evaluation_note}</div>
          </td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  });
}

// ==========================================
// ROLE SWITCHER
// ==========================================
function toggleRoleMenu() {
  const m = document.getElementById("role-menu");
  m.style.display = m.style.display === "none" ? "block" : "none";
}

function loginAsDemo(role) {
  fetch(`/api/auth/demo-login/${role}`)
    .then(res => res.json())
    .then(data => {
      state.currentRole = role;
      document.getElementById("current-user-role-badge").innerText = data.user.name;
      toggleRoleMenu();
      if (role === "judge") switchView("judge");
      else switchView("voice");
    });
}
