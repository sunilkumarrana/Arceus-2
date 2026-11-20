/**
 * सुविधा वाणी (SuvidhaVani) - Client Application Controller
 * Continuous Conversational Voice Loop (Auto-restarting Mic, ChatGPT-style Orb,
 * Real-time Interim STT, Acoustic TTS, and SIH Judge Benchmark Suite).
 */

// Application Global State
const state = {
  sessionId: "session_" + Math.random().toString(36).substring(2, 9),
  language: "hi", // default to Hindi
  voiceOutputEnabled: true,
  currentRole: "citizen",
  activeView: "landing",
  currentProfile: {},
  evaluations: [],
  catalogSchemes: [],
  
  // Continuous Voice State
  voiceConversationActive: false, // True when user wants mic to stay on
  isListening: false,
  isAgentSpeaking: false,
  recognition: null,
  restartTimer: null,
  silenceTimer: null,
  accumulatedTranscript: "",
  turnCount: 0
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  initSpeech();
  loadCatalogData();
});

// ==========================================
// STARTING PAGE / ONBOARDING FLOW
// ==========================================
function continueWithAIAgent() {
  const name = document.getElementById("landing-name").value.trim();
  const occ = document.getElementById("landing-occupation").value;
  const userState = document.getElementById("landing-state").value;
  const lang = document.getElementById("landing-lang").value;

  state.language = lang;
  document.getElementById("app-lang-select").value = lang;

  if (name) state.currentProfile.name = name;
  if (occ) state.currentProfile.occupation = occ;
  if (userState) state.currentProfile.state = userState;

  // Activate continuous conversational voice mode
  state.voiceConversationActive = true;

  // Switch to Voice Orb Screen
  switchView("voice");

  // Format initial greeting
  let introMsg = "";
  if (name && occ) {
    introMsg = lang === "hi"
      ? `नमस्ते ${name} जी! आपका स्वागत है। मुझे पता चला कि आप ${occ === 'farmer' ? 'किसान' : occ} हैं। आप मुझे अपनी आयु, ज़मीन या पारिवारिक आय के बारे में बताएं, मैं आपकी सरकारी योजनाओं की जाँच करूँगी।`
      : `Hello ${name}! Welcome. I see you are working in ${occ}. Please tell me your age, income, or landholding details so I can verify your welfare benefits.`;
  } else if (name) {
    introMsg = lang === "hi"
      ? `नमस्ते ${name} जी! मैं सुविधा वाणी हूँ। आप अपने व्यवसाय और परिवार के बारे में बताएं, मैं आपके लिए सबसे उपयुक्त सरकारी योजनाओं का पता लगाऊँगी।`
      : `Hello ${name}! I am Suvidha Vani. Tell me about your livelihood and family, and I will find the best government schemes for you.`;
  } else {
    introMsg = lang === "hi"
      ? "नमस्ते! मैं सुविधा वाणी हूँ, आपका सरकारी योजना सहायक। आप बोलकर या लिखकर बताएं कि आप क्या काम करते हैं और आपकी क्या आवश्यकता है?"
      : "Hello! I am Suvidha Vani, your voice assistant for Government Schemes. Tell me about what work you do or what support you need.";
  }

  setOrbCaption(introMsg);
  
  // Play speech; when speech finishes, the continuous mic will automatically engage!
  playSpeech(introMsg, lang, () => {
    if (state.voiceConversationActive) {
      startListeningSafe();
    }
  });

  updateSlotInspector(state.currentProfile);
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
  // CONTINUOUS = TRUE keeps listening through pauses!
  state.recognition.continuous = true;
  // INTERIM RESULTS = TRUE shows text in real-time as user speaks
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

      // Silence Detection: wait for 1.3 seconds of pause after user stops speaking, then submit!
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

    // If "no-speech" or "aborted", DO NOT turn off mic if user wants voice conversation!
    if (event.error === "no-speech" || event.error === "aborted") {
      // Keep state active, onend will auto-restart
      return;
    }

    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      state.voiceConversationActive = false;
      state.isListening = false;
      updateMicUI(false);
      setOrbListening(false);
      document.getElementById("orb-status-indicator").innerText = "⚠️ Mic permission blocked in browser settings";
      return;
    }
  };

  state.recognition.onend = () => {
    state.isListening = false;
    
    // AUTO-RESTART LOOP:
    // If voice conversation is active and AI is not speaking and we are on voice view, RESTART IMMEDIATELY!
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
  } catch (e) {
    // If recognition is already starting/active, ignore DOMException
  }
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
    // Explicit User Toggle OFF
    state.voiceConversationActive = false;
    stopListeningForAgent();
    document.getElementById("orb-status-indicator").innerText = "🎙️ Mic Muted • Tap to Speak";
  } else {
    // Explicit User Toggle ON (Continuous Conversational Mode)
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

  // Prevent mic from listening to agent's own speech output
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
    
    // Once agent finishes speaking, automatically resume listening if in conversational mode!
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

// ==========================================
// VIEW ROUTING
// ==========================================
function switchView(viewName) {
  state.activeView = viewName;

  // If navigating away from voice view, pause recognition
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
  document.getElementById("app-lang-select").value = lang;
}

// ==========================================
// VOICE CONVERSATION LOGIC
// ==========================================
function submitUserMessage(optionalText) {
  const inputEl = document.getElementById("chat-text-input");
  const text = (optionalText || inputEl.value || "").trim();
  if (!text) return;

  // Stop listening while server processes and AI responds
  stopListeningForAgent();

  inputEl.value = "";
  document.getElementById("orb-status-indicator").innerText = "⏳ Evaluating Rules & Schemes...";
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
    handleAgentResponse(data);
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

function sendQuickPrompt(promptText) {
  const drawer = document.getElementById("quick-prompts-drawer");
  if (drawer) drawer.style.display = "none";
  state.voiceConversationActive = true;
  submitUserMessage(promptText);
}

function toggleQuickPromptsDrawer() {
  const d = document.getElementById("quick-prompts-drawer");
  if (!d) return;
  d.style.display = d.style.display === "none" ? "block" : "none";
}

function handleAgentResponse(data) {
  state.turnCount = data.questions_asked_count || 0;
  state.currentProfile = data.caller_profile || {};
  state.evaluations = data.schemes_evaluation || [];

  const spoken = data.spoken_text || data.agent_message_hi || data.agent_message_en;
  setOrbCaption(spoken);

  // Play speech with automatic mic restart callback
  playSpeech(spoken, data.current_language || state.language, () => {
    if (state.voiceConversationActive && state.activeView === "voice") {
      startListeningSafe();
    }
  });

  // Update floating match pill
  const eligibleSchemes = state.evaluations.filter(e => e.status === "ELIGIBLE");
  const floatingPill = document.getElementById("floating-match-pill");
  const floatingCount = document.getElementById("floating-match-count");

  if (eligibleSchemes.length > 0) {
    floatingPill.style.display = "inline-flex";
    floatingCount.innerText = `🎉 ${eligibleSchemes.length} Scheme(s) Eligible (${eligibleSchemes.map(s => s.name_en.split('(')[0].trim()).slice(0, 2).join(", ")})`;
  } else {
    floatingPill.style.display = "none";
  }

  updateSlotInspector(data.caller_profile);
  updateDrawerMatches(data.schemes_evaluation);
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
    const greeting = data.greeting_message || "नमस्ते! मैं सुविधा वाणी हूँ, आपका सरकारी योजना सहायक। आप क्या काम करते हैं और क्या सहायता चाहते हैं?";
    setOrbCaption(greeting);
    updateSlotInspector({});
    updateDrawerMatches([]);
    document.getElementById("floating-match-pill").style.display = "none";
    document.getElementById("orb-status-indicator").innerText = "🎙️ Tap Orb or Mic to Speak";
  });
}

// ==========================================
// DETAILS DRAWER (LIVE SLOTS & SCHEMES)
// ==========================================
function openDetailsDrawer() {
  document.getElementById("details-drawer-modal").classList.add("active");
  updateSlotInspector(state.currentProfile);
  updateDrawerMatches(state.evaluations);
}

function closeDetailsDrawer() {
  document.getElementById("details-drawer-modal").classList.remove("active");
}

function updateSlotInspector(profile) {
  const p = profile || {};
  document.getElementById("slot-age").innerText = p.age ? `${p.age} yrs` : "--";
  document.getElementById("slot-occupation").innerText = p.occupation ? p.occupation : "--";
  document.getElementById("slot-income").innerText = p.annual_income ? `₹${p.annual_income.toLocaleString('en-IN')}` : "--";
  document.getElementById("slot-land").innerText = p.has_land ? `${p.land_ha || 1} ha` : (p.has_land === false ? "Landless" : "--");
  document.getElementById("slot-area").innerText = p.area_type || "--";
  document.getElementById("slot-house").innerText = p.house_type || "--";
  document.getElementById("slot-bpl").innerText = p.bpl_status ? "BPL (Yes)" : (p.bpl_status === false ? "No" : "--");
  document.getElementById("slot-tax").innerText = p.is_tax_payer ? "Taxpayer" : (p.is_tax_payer === false ? "Non-Taxpayer" : "--");

  document.querySelectorAll(".slot-val").forEach(el => {
    if (el.innerText !== "--") el.classList.remove("empty");
    else el.classList.add("empty");
  });
}

function updateDrawerMatches(evaluations) {
  const container = document.getElementById("drawer-matches-list");
  if (!container) return;
  container.innerHTML = "";

  if (!evaluations || evaluations.length === 0) {
    container.innerHTML = `<div style="font-size:12px; color:#64748B; text-align:center; padding:16px 0;">Speak with the agent to evaluate schemes in real-time.</div>`;
    return;
  }

  evaluations.slice(0, 6).forEach(sch => {
    const card = document.createElement("div");
    card.className = "scheme-card";
    const titleLang = state.language === "hi" ? sch.name_hi : sch.name_en;
    const benefitsLang = state.language === "hi" ? sch.benefits_hi : sch.benefits_en;

    card.innerHTML = `
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <span class="status-badge ${sch.status.toLowerCase()}">${sch.status.replace('_', ' ')}</span>
          <span style="font-size:11px; color:#64748B;">Score: ${(sch.match_score * 100).toFixed(0)}%</span>
        </div>
        <h3 style="font-size:14px; margin-bottom:4px;">${titleLang}</h3>
        <p style="font-size:12px; color:#475569;">${benefitsLang.substring(0, 95)}...</p>
      </div>
      <div style="margin-top:10px; display:flex; justify-content:space-between;">
        <button class="btn-secondary" style="font-size:11px; padding:4px 8px;" onclick="openExplainModal('${sch.scheme_id}')">Explain Rules</button>
        <button class="btn-primary" style="font-size:11px; padding:4px 8px;" onclick="saveSchemeBookmark('${sch.scheme_id}')">Bookmark</button>
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
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#64748B;">Use the Voice Agent or Profile Form to run deterministic rule matching.</td></tr>`;
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
      item.style.border = "1px solid #E2E8F0";
      item.style.borderRadius = "10px";
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
        recContainer.innerHTML = `<p style="color:#64748B; font-size:13px;">No schemes matched yet. Speak with the Voice Agent to evaluate your benefits.</p>`;
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
