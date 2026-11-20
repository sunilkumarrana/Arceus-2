/**
 * सुविधा वाणी (SuvidhaVani) - Client Application Controller
 * Simple, Clean Workflow:
 * 1. Landing: Clean site details + prominent "Show Schemes" button.
 * 2. Voice Agent: Asks "Which scheme are you looking for?" with active mic.
 * 3. User responds: Agent speaks explanation and shows related schemes directly below the orb.
 */

// Application Global State
const state = {
  sessionId: "session_" + Math.random().toString(36).substring(2, 9),
  language: "hi", // default to Hindi
  voiceOutputEnabled: true,
  activeView: "landing", // starts on the clean landing page
  currentProfile: {},
  evaluations: [],
  catalogSchemes: [],
  
  // Continuous Voice State
  voiceConversationActive: false,
  isListening: false,
  isAgentSpeaking: false,
  recognition: null,
  restartTimer: null,
  silenceTimer: null,
  turnCount: 0
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  initSpeech();
  loadCatalogData();
});

function goToHome() {
  state.voiceConversationActive = false;
  stopListeningForAgent();
  switchView("landing");
}

function toggleLanguageFast() {
  const newLang = state.language === "hi" ? "en" : "hi";
  changeLanguage(newLang);
  document.getElementById("app-lang-select").value = newLang;
}

// ==========================================
// STEP 1 & 2: USER CLICKS "SHOW SCHEMES"
// ==========================================
function startVoiceAgentFlow() {
  switchView("voice");
  state.voiceConversationActive = true;

  // Question the Voice Agent asks immediately:
  const question = state.language === "hi"
    ? "नमस्ते! आप कौन सी सरकारी योजना ढूंढ रहे हैं?"
    : "Hello! Which government scheme are you looking for?";

  setOrbCaption(question);

  // Initially show popular recommended schemes so the screen is not empty
  if (state.catalogSchemes.length > 0) {
    renderRelatedSchemes(state.catalogSchemes.slice(0, 4));
  }

  // Speak the question aloud; when speech completes, continuous mic automatically engages!
  playSpeech(question, state.language, () => {
    if (state.voiceConversationActive) {
      startListeningSafe();
    }
  });
}

function handleSchemeQuickChoice(choiceText) {
  state.voiceConversationActive = true;
  submitUserMessage(choiceText);
}

// ==========================================
// CONTINUOUS SPEECH RECOGNITION (STT)
// ==========================================
function initSpeech() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.info("Web Speech API not supported in this browser. Fallback to text input.");
    return;
  }

  state.recognition = new SpeechRecognition();
  state.recognition.continuous = true;
  state.recognition.interimResults = true;
  state.recognition.lang = state.language === "hi" ? "hi-IN" : "en-IN";

  state.recognition.onstart = () => {
    state.isListening = true;
    updateMicUI(true);
    setOrbListening(true);
    const statusText = state.language === "hi" ? "🔴 माइक चालू है • बोलिए..." : "🔴 Listening... Speak naturally";
    document.getElementById("orb-status-indicator").innerText = statusText;
  };

  state.recognition.onresult = (event) => {
    let interimTranscript = "";
    let finalTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript + " ";
      } else {
        interimTranscript += transcript;
      }
    }

    const currentText = (finalTranscript || interimTranscript).trim();
    if (currentText) {
      document.getElementById("chat-text-input").value = currentText;
      setOrbCaption(`You: "${currentText}"`);

      // Silence Detection: 1.3 seconds of pause after user stops speaking -> submit!
      clearTimeout(state.silenceTimer);
      state.silenceTimer = setTimeout(() => {
        const textToSubmit = document.getElementById("chat-text-input").value.trim();
        if (textToSubmit && textToSubmit.length >= 2) {
          submitUserMessage(textToSubmit);
        }
      }, 1300);
    }
  };

  state.recognition.onerror = (event) => {
    console.warn("Speech recognition event:", event.error);
    if (event.error === "no-speech" || event.error === "aborted") {
      return; // Keep continuous loop alive
    }

    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      state.voiceConversationActive = false;
      state.isListening = false;
      updateMicUI(false);
      setOrbListening(false);
      document.getElementById("orb-status-indicator").innerText = "⚠️ Mic permission blocked in browser settings";
    }
  };

  state.recognition.onend = () => {
    state.isListening = false;
    
    // Auto-Restart keep-alive loop when in voice mode and AI is not speaking
    if (state.voiceConversationActive && !state.isAgentSpeaking && state.activeView === "voice") {
      clearTimeout(state.restartTimer);
      state.restartTimer = setTimeout(() => {
        startListeningSafe();
      }, 250);
    } else {
      updateMicUI(false);
      setOrbListening(false);
      if (!state.isAgentSpeaking) {
        document.getElementById("orb-status-indicator").innerText = "🎙️ Mic Muted • Tap to Speak";
      }
    }
  };
}

function startListeningSafe() {
  if (!state.recognition || state.isListening || state.isAgentSpeaking) return;
  state.recognition.lang = state.language === "hi" ? "hi-IN" : "en-IN";
  try {
    state.recognition.start();
  } catch (e) {}
}

function stopListeningForAgent() {
  clearTimeout(state.restartTimer);
  clearTimeout(state.silenceTimer);
  if (state.recognition && state.isListening) {
    try {
      state.recognition.stop();
    } catch (e) {}
  }
  state.isListening = false;
  updateMicUI(false);
  setOrbListening(false);
}

function toggleVoiceInput() {
  if (!state.recognition) {
    alert("Web Speech API is not supported in this browser. Please type in the input bar below.");
    return;
  }

  if (state.isListening || state.voiceConversationActive) {
    state.voiceConversationActive = false;
    stopListeningForAgent();
    document.getElementById("orb-status-indicator").innerText = "🎙️ Mic Muted • Tap to Speak";
  } else {
    state.voiceConversationActive = true;
    startListeningSafe();
  }
}

function updateMicUI(listening) {
  const micBtn = document.getElementById("mic-btn");
  if (!micBtn) return;
  if (listening) {
    micBtn.classList.add("listening");
    micBtn.innerHTML = "🔴";
  } else {
    micBtn.classList.remove("listening");
    micBtn.innerHTML = "🎤";
  }
}

function setOrbListening(listening) {
  const orb = document.getElementById("main-voice-orb");
  if (!orb) return;
  if (listening) {
    orb.classList.add("listening");
    orb.classList.remove("speaking");
  } else {
    orb.classList.remove("listening");
  }
}

function setOrbSpeaking(speaking) {
  const orb = document.getElementById("main-voice-orb");
  if (!orb) return;
  if (speaking) {
    orb.classList.add("speaking");
    orb.classList.remove("listening");
  } else {
    orb.classList.remove("speaking");
  }
}

function setOrbCaption(text) {
  const captionEl = document.getElementById("voice-caption-text");
  if (captionEl) {
    captionEl.innerText = `"${text}"`;
  }
}

// ==========================================
// SPEECH SYNTHESIS (TTS)
// ==========================================
function playSpeech(text, lang, onEndCallback) {
  if (!state.voiceOutputEnabled || !window.speechSynthesis) {
    if (onEndCallback) onEndCallback();
    return;
  }

  stopListeningForAgent();
  state.isAgentSpeaking = true;

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang === "hi" ? "hi-IN" : "en-IN";
  utterance.rate = 0.95;

  const voices = window.speechSynthesis.getVoices();
  const indianVoice = voices.find(v => v.lang.includes("IN") || v.name.includes("India") || (lang === "hi" && v.lang.startsWith("hi")));
  if (indianVoice) {
    utterance.voice = indianVoice;
  }

  utterance.onstart = () => {
    setOrbSpeaking(true);
    document.getElementById("orb-status-indicator").innerText = "🔊 Suvidha AI Speaking...";
  };

  utterance.onend = () => {
    state.isAgentSpeaking = false;
    setOrbSpeaking(false);
    if (onEndCallback) {
      onEndCallback();
    } else if (state.voiceConversationActive && state.activeView === "voice") {
      startListeningSafe();
    } else {
      document.getElementById("orb-status-indicator").innerText = "🎙️ Tap Orb or Mic to Speak";
    }
  };

  utterance.onerror = () => {
    state.isAgentSpeaking = false;
    setOrbSpeaking(false);
    if (state.voiceConversationActive && state.activeView === "voice") {
      startListeningSafe();
    }
  };

  window.speechSynthesis.speak(utterance);
}

function toggleAudioOutput() {
  state.voiceOutputEnabled = !state.voiceOutputEnabled;
  const btn = document.getElementById("voice-toggle-btn");
  const icon = document.getElementById("voice-icon");
  if (state.voiceOutputEnabled) {
    btn.classList.add("active");
    btn.innerHTML = `<span id="voice-icon">🔊</span> Voice ON`;
  } else {
    btn.classList.remove("active");
    btn.innerHTML = `<span id="voice-icon">🔇</span> Voice Muted`;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }
}

// ==========================================
// VIEW ROUTING
// ==========================================
function switchView(viewName) {
  state.activeView = viewName;

  if (viewName !== "voice") {
    stopListeningForAgent();
  } else if (state.voiceConversationActive) {
    startListeningSafe();
  }

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

  if (viewName === "catalog") renderCatalog(state.catalogSchemes);
}

function changeLanguage(lang) {
  state.language = lang;
  if (state.recognition) {
    state.recognition.lang = lang === "hi" ? "hi-IN" : "en-IN";
  }
  document.getElementById("app-lang-select").value = lang;
}

// ==========================================
// STEP 3: USER ANSWERS -> SHOW RELATED SCHEMES
// ==========================================
function submitUserMessage(optionalText) {
  const inputEl = document.getElementById("chat-text-input");
  const text = (optionalText || inputEl.value || "").trim();
  if (!text) return;

  stopListeningForAgent();
  inputEl.value = "";
  document.getElementById("orb-status-indicator").innerText = "⏳ Finding Related Schemes...";
  setOrbCaption(`You: "${text}"`);

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
    handleAgentResponse(data, text);
  })
  .catch(err => {
    console.error("Chat turn error:", err);
    const errMsg = "माफ कीजिये, सर्वर से संपर्क नहीं हो पाया। कृपया पुनः प्रयास करें।";
    setOrbCaption(errMsg);
    playSpeech(errMsg, state.language, () => {
      if (state.voiceConversationActive) startListeningSafe();
    });
  });
}

function handleInputKey(event) {
  if (event.key === "Enter") {
    submitUserMessage();
  }
}

function handleAgentResponse(data, userUtterance) {
  state.turnCount = data.questions_asked_count || 0;
  state.currentProfile = data.caller_profile || {};
  state.evaluations = data.schemes_evaluation || [];

  const spoken = data.spoken_text || data.agent_message_hi || data.agent_message_en;
  setOrbCaption(spoken);

  // Speak agent response aloud, then re-engage mic
  playSpeech(spoken, data.current_language || state.language, () => {
    if (state.voiceConversationActive && state.activeView === "voice") {
      startListeningSafe();
    }
  });

  // RENDER THE RELATED SCHEMES DIRECTLY ON THE SCREEN!
  renderRelatedSchemes(data.schemes_evaluation);
}

function renderRelatedSchemes(schemes) {
  const container = document.getElementById("related-schemes-cards");
  const titleEl = document.getElementById("related-schemes-title");
  const badgeEl = document.getElementById("related-count-badge");
  if (!container) return;

  container.innerHTML = "";

  if (!schemes || schemes.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:20px; color:#64748B;">No matching schemes found yet. Try asking for farming, healthcare, pension, or loans.</div>`;
    return;
  }

  // Display top 4 to 6 most relevant schemes
  const displaySchemes = schemes.slice(0, 6);
  badgeEl.innerText = `${displaySchemes.length} Schemes Found`;

  displaySchemes.forEach(s => {
    const card = document.createElement("div");
    card.className = "scheme-card";

    const title = state.language === "hi" ? (s.name_hi || s.name_en) : (s.name_en || s.name_hi);
    const benefits = state.language === "hi" ? (s.benefits_hi || s.benefits_en) : (s.benefits_en || s.benefits_hi);
    const category = s.category || "General";
    const status = s.status || "ELIGIBLE";
    const statusClass = status.toLowerCase();

    card.innerHTML = `
      <div>
        <div class="scheme-tags-bar">
          <span class="status-badge ${statusClass}">${status.replace('_', ' ')}</span>
          <span class="scheme-tag">${category}</span>
          <span class="scheme-tag" style="background:#EFF6FF; color:#1E40AF;">Verified</span>
        </div>
        <h3 style="font-size:15px; margin-bottom:6px;">${title}</h3>
        <div class="scheme-benefits-box" style="margin-bottom:10px;">
          <strong>Benefit:</strong> ${benefits.substring(0, 115)}...
        </div>
      </div>
      <div class="scheme-card-footer">
        <a href="${s.portal_url || '#'}" target="_blank" style="font-size:12px; color:#1E3A8A; font-weight:700; text-decoration:none;">Apply Online ↗</a>
        <div style="display:flex; gap:6px;">
          <button class="btn-primary" style="font-size:11px; padding:4px 10px; border-radius:9999px;" onclick="openExplainModal('${s.scheme_id || s.id}')">
            Check Details & Rules
          </button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function resetConversation() {
  state.voiceConversationActive = false;
  stopListeningForAgent();

  fetch("/api/chat/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId, language: state.language })
  })
  .then(res => res.json())
  .then(data => {
    const greeting = "नमस्ते! आप कौन सी सरकारी योजना ढूंढ रहे हैं?";
    setOrbCaption(greeting);
    document.getElementById("orb-status-indicator").innerText = "🎙️ Mic Muted • Tap Orb or Mic to Speak";
    if (state.catalogSchemes.length > 0) {
      renderRelatedSchemes(state.catalogSchemes.slice(0, 4));
    }
  });
}

// ==========================================
// EXPLAINABILITY MODAL
// ==========================================
function openExplainModal(schemeId) {
  const schemeEval = state.evaluations.find(e => (e.scheme_id === schemeId || e.id === schemeId));
  const rawScheme = state.catalogSchemes.find(s => s.id === schemeId);
  const modal = document.getElementById("explain-modal");
  if (!schemeEval && !rawScheme) return;

  const title = state.language === "hi" ? (schemeEval?.name_hi || rawScheme?.name_hi) : (schemeEval?.name_en || rawScheme?.name_en);
  const benefits = state.language === "hi" ? (schemeEval?.benefits_hi || rawScheme?.benefits_hi) : (schemeEval?.benefits_en || rawScheme?.benefits_en);
  const status = schemeEval ? schemeEval.status : "ELIGIBLE";

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
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#64748B;">Official Government scheme criteria verified against myScheme standard rules.</td></tr>`;
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
// ALL SCHEMES CATALOG
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
          <button class="btn-primary" style="font-size:11px; padding:4px 8px;" onclick="quickAskScheme('${s.id}')">Ask AI</button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function quickAskScheme(schemeId) {
  startVoiceAgentFlow();
  setTimeout(() => {
    submitUserMessage(`मुझे ${schemeId} योजना के बारे में बताएं`);
  }, 400);
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

// ==========================================
// SIH JUDGE BENCHMARK SUITE
// ==========================================
function loadScenarioToVoice(scenarioId) {
  startVoiceAgentFlow();

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
      submitUserMessage(text);
    }, 500);
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
