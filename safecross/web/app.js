"use strict";

(() => {
  const API = "/api/v1/safecross";
  const byId = (id) => document.getElementById(id);
  const video = byId("source-video");
  const canvas = byId("overlay");
  const ctx = canvas.getContext("2d");
  const state = { job: null, roi: [], editing: false, blobUrl: null, pollTimer: null, requestSerial: 0, status: null, submitting: false, localFile: null, previewLoadedFor: null };

  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  };
  const isBusy = () => state.submitting || (state.job && ["queued", "running"].includes(state.job.status));
  const mediaUrl = (file) => `${API}/jobs/${encodeURIComponent(state.job.job_id)}/media/${encodeURIComponent(file)}`;
  const timeLabel = (value) => {
    const seconds = Math.max(0, Number(value) || 0);
    const whole = Math.floor(seconds);
    return `${String(Math.floor(whole / 60)).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}.${Math.floor((seconds - whole) * 10)}`;
  };
  function message(text, isError = false) {
    const box = byId("global-message");
    box.textContent = text || "";
    box.classList.toggle("hidden", !text);
    box.classList.toggle("error", isError);
  }
  function errorText(value) {
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map((item) => `${(item.loc || []).slice(1).join(" / ")}: ${item.msg || "Valoare invalidă"}`).join("; ");
    if (value && typeof value === "object") return value.message || value.msg || value.code || "Cererea nu a putut fi procesată.";
    return "Cererea nu a putut fi procesată.";
  }
  async function request(url, options = {}) {
    const response = await fetch(url, { ...options, signal: AbortSignal.timeout(120000) });
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(errorText(payload && (payload.detail || payload.error || payload)));
    if (!payload) throw new Error("Serverul a returnat un răspuns fără date JSON.");
    return payload;
  }

  function setEditing(value) {
    state.editing = value;
    if (value) video.pause();
    canvas.classList.toggle("editing", value);
    byId("edit-roi").setAttribute("aria-pressed", String(value));
    byId("edit-roi").textContent = value ? "Încheie delimitarea" : "Delimitează zona în imagine";
  }
  function updateRoi() {
    byId("roi-json").value = state.roi.length ? JSON.stringify(state.roi) : "";
    byId("roi-status").textContent = state.roi.length ? `${state.roi.length} puncte${state.roi.length < 3 ? " · mai sunt necesare puncte pentru un poligon" : " · poligon pregătit"}` : "Întregul cadru · fără zonă delimitată";
    drawOverlay();
  }
  function readRoi() {
    const raw = byId("roi-json").value.trim();
    if (!raw) return [];
    let roi;
    try { roi = JSON.parse(raw); } catch { throw new Error("Zona nu este un JSON valid. Folosește o listă de perechi [x, y]."); }
    if (!Array.isArray(roi) || roi.length < 3 || roi.length > 12 || roi.some((point) => !Array.isArray(point) || point.length !== 2 || point.some((value) => typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1))) {
      throw new Error("Zona trebuie să aibă între 3 și 12 puncte [x, y], cu valori între 0 și 1.");
    }
    return roi;
  }
  function frameSize() {
    const metadata = state.job && state.job.result && state.job.result.video;
    return { width: (metadata && metadata.width) || video.videoWidth || 1280, height: (metadata && metadata.height) || video.videoHeight || 720 };
  }
  function drawOverlay() {
    const size = frameSize();
    const bounds = video.getBoundingClientRect();
    if (bounds.width && bounds.height) {
      const factor = Math.min(bounds.width / size.width, bounds.height / size.height);
      const width = size.width * factor;
      const height = size.height * factor;
      Object.assign(canvas.style, { width: `${width}px`, height: `${height}px`, left: `${(bounds.width - width) / 2}px`, top: `${(bounds.height - height) / 2}px` });
    }
    if (canvas.width !== size.width || canvas.height !== size.height) { canvas.width = size.width; canvas.height = size.height; }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const scale = Math.max(1, canvas.width / 900);
    if (state.roi.length) {
      ctx.beginPath();
      state.roi.forEach(([x, y], index) => index ? ctx.lineTo(x * canvas.width, y * canvas.height) : ctx.moveTo(x * canvas.width, y * canvas.height));
      if (state.roi.length >= 3) ctx.closePath();
      ctx.fillStyle = "rgba(191, 221, 113, 0.12)";
      ctx.fill();
      ctx.strokeStyle = "#c7e78b";
      ctx.lineWidth = 2 * scale;
      ctx.stroke();
      state.roi.forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x * canvas.width, y * canvas.height, 4 * scale, 0, Math.PI * 2); ctx.fillStyle = "#def6ad"; ctx.fill(); });
    }
    const frames = state.job && state.job.result && state.job.result.frames;
    if (!byId("show-tracks").checked || !Array.isArray(frames) || !frames.length) return;
    const current = video.currentTime;
    let closest = null;
    let distance = Infinity;
    for (const frame of frames) {
      const gap = Math.abs(Number(frame.time_s) - current);
      if (gap < distance) { closest = frame; distance = gap; }
    }
    const sampleFps = (state.job.result.parameters && state.job.result.parameters.effective_sample_fps) || (state.status && state.status.limits && state.status.limits.sample_fps) || 2;
    if (!closest || distance > Math.max(0.7, 1.1 / sampleFps)) return;
    for (const object of closest.objects || []) {
      const bbox = object.bbox;
      if (!Array.isArray(bbox) || bbox.length !== 4 || bbox.some((value) => !Number.isFinite(value))) continue;
      const [x1, y1, x2, y2] = bbox;
      const person = object.label === "person";
      const color = person ? "#c7ef93" : "#81ceee";
      const recent = frames.filter((frame) => Number(frame.time_s) <= current && Number(frame.time_s) >= current - 1.5);
      ctx.beginPath();
      let hasPath = false;
      for (const frame of recent) {
        const previous = (frame.objects || []).find((item) => item.track_id === object.track_id);
        if (!previous || !Array.isArray(previous.bbox) || previous.bbox.length !== 4) continue;
        const [left, , right, bottom] = previous.bbox;
        if (hasPath) ctx.lineTo((left + right) / 2, bottom); else ctx.moveTo((left + right) / 2, bottom);
        hasPath = true;
      }
      ctx.strokeStyle = color;
      ctx.lineWidth = 2 * scale;
      ctx.globalAlpha = 0.6;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2 * scale;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.font = `${12 * scale}px sans-serif`;
      const title = `${object.label || "obiect"} · ${object.track_id ?? "?"}`;
      const width = ctx.measureText(title).width + 10 * scale;
      const labelY = Math.max(0, y1 - 20 * scale);
      ctx.fillStyle = color;
      ctx.fillRect(x1, labelY, width, 20 * scale);
      ctx.fillStyle = "#143126";
      ctx.fillText(title, x1 + 5 * scale, labelY + 14 * scale);
    }
  }
  const animate = () => { if (!video.paused && !video.ended) drawOverlay(); requestAnimationFrame(animate); };
  requestAnimationFrame(animate);
  ["loadedmetadata", "seeked", "timeupdate", "pause"].forEach((event) => video.addEventListener(event, drawOverlay));
  byId("show-tracks").addEventListener("change", drawOverlay);
  byId("edit-roi").addEventListener("click", () => setEditing(!state.editing));
  byId("clear-roi").addEventListener("click", () => { state.roi = []; updateRoi(); });
  byId("roi-json").addEventListener("change", () => {
    try { state.roi = readRoi(); updateRoi(); message(""); } catch (error) { message(error.message, true); }
  });
  canvas.addEventListener("click", (event) => {
    if (!state.editing || isBusy()) return;
    if (state.roi.length >= 12) { message("Zona poate avea cel mult 12 puncte.", true); return; }
    const rect = canvas.getBoundingClientRect();
    const intrinsic = frameSize();
    const factor = Math.min(rect.width / intrinsic.width, rect.height / intrinsic.height);
    const actualWidth = intrinsic.width * factor;
    const actualHeight = intrinsic.height * factor;
    const x = (event.clientX - rect.left - (rect.width - actualWidth) / 2) / actualWidth;
    const y = (event.clientY - rect.top - (rect.height - actualHeight) / 2) / actualHeight;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    state.roi.push([Number(x.toFixed(5)), Number(y.toFixed(5))]);
    updateRoi();
  });

  function updateControls() {
    const busy = isBusy();
    const saved = Boolean(state.job);
    const modelUnavailable = state.status && (!state.status.available || !state.status.model_ready);
    byId("analyze-button").disabled = Boolean(busy || modelUnavailable);
    byId("analyze-button").firstElementChild.textContent = busy ? "Analiză în curs…" : "Analizează clipul";
    byId("video-file").disabled = Boolean(busy);
    ["data-mode", "fixed-camera", "roi-json", "clear-roi", "source-url", "attribution", "license"].forEach((id) => { byId(id).disabled = Boolean(busy || saved); });
    byId("edit-roi").disabled = Boolean(busy || saved || !video.src);
    if (saved) byId("roi-status").textContent = `${state.roi.length ? `${state.roi.length} puncte · ` : ""}Zona analizei este salvată. Selectează din nou clipul pentru altă configurare.`;
  }
  function displayMode(mode) {
    const badge = byId("mode-badge");
    badge.textContent = mode === "observed" ? "Observat" : "Sintetic / demonstrație";
    badge.classList.remove("hidden");
    badge.classList.toggle("observed", mode === "observed");
  }
  byId("data-mode").addEventListener("change", () => { if (!state.job) displayMode(byId("data-mode").value); });
  byId("video-file").addEventListener("click", () => { if (state.job && !isBusy()) byId("video-file").value = ""; });
  byId("video-file").addEventListener("change", () => {
    const file = byId("video-file").files[0];
    if (!file) return;
    clearTimeout(state.pollTimer);
    state.requestSerial += 1;
    state.job = null;
    state.previewLoadedFor = null;
    state.localFile = file;
    state.roi = [];
    setEditing(false);
    updateRoi();
    if (state.blobUrl) URL.revokeObjectURL(state.blobUrl);
    state.blobUrl = URL.createObjectURL(file);
    video.src = state.blobUrl;
    byId("empty-video").classList.add("hidden");
    byId("video-wrap").classList.remove("hidden");
    byId("file-name").textContent = `${file.name} · ${(file.size / (1024 * 1024)).toFixed(1)} MB`;
    byId("video-metadata").textContent = "Previzualizare locală · încă neanalizată";
    byId("analysis-meta").classList.add("hidden");
    byId("processing").classList.add("hidden");
    byId("export-button").classList.add("hidden");
    byId("candidate-count").textContent = "0";
    byId("candidates").replaceChildren(node("p", "empty-results", "Clipul este pregătit. Pornește analiza pentru a căuta interacțiuni candidate."));
    displayMode(byId("data-mode").value);
    updateControls();
    message("");
    const maxBytes = state.status && state.status.limits && state.status.limits.max_upload_bytes;
    if (maxBytes && file.size > maxBytes) message(`Fișierul depășește limita de ${(maxBytes / 1048576).toFixed(0)} MB. Alege un clip mai scurt.`, true);
  });
  video.addEventListener("loadedmetadata", () => {
    const duration = Number.isFinite(video.duration) ? ` · ${timeLabel(video.duration)}` : "";
    byId("video-metadata").textContent = `${video.videoWidth} × ${video.videoHeight}${duration}${state.job ? " · analiză salvată" : " · previzualizare locală"}`;
  });
  video.addEventListener("error", () => message("Browserul nu poate reda acest codec. Încearcă un clip MP4 H.264; analiza nu transformă automat sursa într-un format compatibil.", true));

  async function loadStatus() {
    try {
      state.status = await request(`${API}/status`);
      const ready = Boolean(state.status.available && state.status.model_ready);
      const name = state.status.model && state.status.model.name;
      byId("model-dot").classList.toggle("ready", ready);
      byId("model-dot").classList.toggle("unready", !ready);
      byId("model-status").textContent = ready ? `Motor pregătit${name ? ` · ${name}` : ""}` : (state.status.message || "Modelul nu este pregătit pe server");
      const limits = state.status.limits || {};
      const parts = [];
      if (limits.max_upload_bytes) parts.push(`maximum ${(limits.max_upload_bytes / 1048576).toFixed(0)} MB`);
      if (limits.max_duration_s) parts.push(`${limits.max_duration_s} secunde`);
      if (limits.sample_fps) parts.push(`${limits.sample_fps} cadre analizate/s`);
      byId("upload-limits").textContent = parts.length ? parts.join(" · ") : "Consultă limitele în documentația API.";
      if (!ready) message(state.status.message || "Motorul de analiză necesită configurarea modelului pe server. Poți pregăti clipul și zona între timp.");
    } catch (error) {
      byId("model-status").textContent = "Motorul nu a putut fi verificat";
      byId("model-dot").classList.add("unready");
      byId("upload-limits").textContent = "Limitele nu au putut fi încărcate. Serverul va valida fișierul.";
      message(`Nu am putut verifica starea motorului: ${error.message}`, true);
    }
    updateControls();
  }

  function jumpTo(seconds) {
    setEditing(false);
    video.currentTime = Math.max(0, Number(seconds) || 0);
    video.pause();
    drawOverlay();
    byId("video-heading").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function reviewOf(candidate) {
    return (state.job.reviews && state.job.reviews[candidate.candidate_id]) || candidate.review || null;
  }
  function renderCandidates() {
    const container = byId("candidates");
    const candidates = (state.job.result && state.job.result.candidates) || [];
    byId("candidate-count").textContent = String(candidates.length);
    container.replaceChildren();
    if (!candidates.length) {
      byId("results-description").textContent = state.job.status === "completed"
        ? "0 candidați semnalați în acest clip. Absența candidaților nu certifică siguranța locației."
        : state.job.status === "failed"
          ? "Analiza a eșuat. Nu sunt disponibile rezultate pentru revizuire."
          : "Analiza este în curs. Numărul candidaților va fi disponibil după finalizare.";
      container.append(node("p", "empty-results", state.job.status === "completed" ? "Nu au fost semnalate interacțiuni candidate în acest clip. Acest rezultat nu certifică siguranța locației." : state.job.status === "failed" ? "Nu au fost publicate rezultate parțiale. Verifică mesajul de eroare înainte de o nouă analiză." : "Analiza pregătește dovezile pentru revizuire."));
      return;
    }
    let confirmed = 0;
    let dismissed = 0;
    for (const [index, candidate] of candidates.entries()) {
      const review = reviewOf(candidate);
      if (review && review.decision === "confirmed") confirmed += 1;
      if (review && review.decision === "dismissed") dismissed += 1;
      const card = node("article", "candidate-card");
      const seekButton = node("button", "candidate-image-button");
      seekButton.type = "button";
      seekButton.setAttribute("aria-label", `Vezi interacțiunea ${index + 1} la ${timeLabel(candidate.representative_s ?? candidate.start_s)}`);
      seekButton.addEventListener("click", () => jumpTo(candidate.representative_s ?? candidate.start_s));
      if (candidate.snapshot && typeof candidate.snapshot === "string" && !candidate.snapshot.includes("/") && !candidate.snapshot.includes("\\")) {
        const image = node("img");
        image.src = mediaUrl(candidate.snapshot);
        image.alt = `Cadru pentru interacțiunea candidată ${index + 1}`;
        image.loading = "lazy";
        image.addEventListener("error", () => { image.replaceWith(node("span", "image-placeholder", "Vezi momentul în filmare")); });
        seekButton.append(image);
      } else seekButton.append(node("span", "image-placeholder", "Vezi momentul în filmare"));
      seekButton.append(node("span", "timestamp", `${timeLabel(candidate.start_s)} – ${timeLabel(candidate.end_s)}`));
      card.append(seekButton);
      const body = node("div", "candidate-body");
      const titleRow = node("div", "candidate-title-row");
      titleRow.append(node("h3", "", `Interacțiunea ${String(index + 1).padStart(2, "0")}`));
      const decision = review && review.decision;
      const badgeText = decision === "confirmed" ? "Confirmată vizual" : decision === "dismissed" ? "Respinsă" : "De verificat";
      titleRow.append(node("span", `review-badge${decision ? ` ${decision}` : ""}`, badgeText));
      body.append(titleRow);
      body.append(node("p", "candidate-reason", candidate.reason || "Apropiere semnalată între traiectorii; verifică secvența și contextul."));
      body.append(node("p", "track-info", `Persoană #${candidate.person_track_id ?? "?"} · vehicul #${candidate.vehicle_track_id ?? "?"}`));
      const noteId = `review-note-${index}`;
      const label = node("label", "", "Nota operatorului");
      label.htmlFor = noteId;
      const note = node("textarea", "review-note");
      note.id = noteId;
      note.rows = 2;
      note.maxLength = 2000;
      note.placeholder = "Ce se vede în filmare?";
      note.value = (review && review.note) || "";
      body.append(label, note);
      const actions = node("div", "review-actions");
      const confirm = node("button", "confirm-button", "Confirmă interacțiunea");
      const dismiss = node("button", "dismiss-button", "Respinge candidatul");
      confirm.type = dismiss.type = "button";
      const inlineError = node("p", "candidate-error hidden");
      inlineError.setAttribute("role", "alert");
      const saveReview = async (decisionValue) => {
        const operator = byId("operator").value.trim();
        if (!operator) { inlineError.textContent = "Completează numele operatorului înainte de verificare."; inlineError.classList.remove("hidden"); byId("operator").focus(); return; }
        confirm.disabled = dismiss.disabled = true;
        inlineError.classList.add("hidden");
        try {
          state.job = await request(`${API}/jobs/${encodeURIComponent(state.job.job_id)}/candidates/${encodeURIComponent(candidate.candidate_id)}/review`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ expected_version: state.job.version, operator, decision: decisionValue, note: note.value.trim() })
          });
          renderJob();
        } catch (error) {
          inlineError.textContent = `${error.message} Reîncearcă după actualizarea analizei.`;
          inlineError.classList.remove("hidden");
          confirm.disabled = dismiss.disabled = false;
          try { state.job = await request(`${API}/jobs/${encodeURIComponent(state.job.job_id)}`); } catch { /* Keep the visible error and review text. */ }
        }
      };
      confirm.addEventListener("click", () => saveReview("confirmed"));
      dismiss.addEventListener("click", () => saveReview("dismissed"));
      actions.append(confirm, dismiss);
      body.append(actions, inlineError);
      if (review) body.append(node("p", "review-detail", `Verificat de ${review.operator || "operator"}${review.at ? ` · ${new Date(review.at).toLocaleString("ro-RO")}` : ""}. Confirmarea privește interacțiunea vizibilă, nu un accident.`));
      card.append(body);
      container.append(card);
    }
    byId("results-description").textContent = `${candidates.length} candidați · ${confirmed} confirmați vizual · ${dismissed} respinși · ${candidates.length - confirmed - dismissed} de verificat. Selecția nu reprezintă un inventar al accidentelor.`;
  }

  function renderJob() {
    const job = state.job;
    displayMode(job.data_mode);
    byId("processing").classList.remove("hidden");
    const progress = Math.max(0, Math.min(1, Number(job.progress) || 0));
    byId("progress-bar").value = job.status === "completed" ? 1 : progress;
    byId("progress-percent").textContent = `${Math.round((job.status === "completed" ? 1 : progress) * 100)}%`;
    const titles = { queued: "Clipul este în așteptare", running: "Analiza este în curs pe server", completed: "Analiză finalizată · rezultate salvate", failed: "Analiza nu a putut fi finalizată" };
    byId("progress-title").textContent = titles[job.status] || job.status;
    byId("progress-detail").textContent = job.status === "completed" ? "Redarea filmării și a detecțiilor folosește analiza salvată; nu este o nouă procesare live." : job.status === "failed" ? errorText(job.error) : "AI-ul detectează persoane și vehicule. Procesarea se desfășoară pe server.";
    byId("analysis-meta").classList.remove("hidden");
    const metadata = [`Analiză ${job.job_id}`, `versiunea ${job.version}`, job.created_at ? new Date(job.created_at).toLocaleString("ro-RO") : ""].filter(Boolean);
    byId("analysis-meta").textContent = metadata.join(" · ");
    byId("export-button").href = `${API}/jobs/${encodeURIComponent(job.job_id)}/export`;
    byId("export-button").classList.toggle("hidden", job.status !== "completed");
    if (job.status === "completed" && job.result && job.result.preview_available && state.previewLoadedFor !== job.job_id) {
      const position = video.currentTime;
      state.previewLoadedFor = job.job_id;
      video.src = mediaUrl("source");
      if (position > 0) video.addEventListener("loadedmetadata", () => { video.currentTime = Math.min(position, Number.isFinite(video.duration) ? video.duration : position); }, { once: true });
      video.load();
    }
    if (job.status === "failed") message(`Analiza a eșuat: ${errorText(job.error)}`, true);
    renderCandidates();
    updateControls();
    drawOverlay();
  }
  function poll(serial) {
    clearTimeout(state.pollTimer);
    if (!state.job || !["queued", "running"].includes(state.job.status) || serial !== state.requestSerial) return;
    state.pollTimer = setTimeout(async () => {
      try {
        const job = await request(`${API}/jobs/${encodeURIComponent(state.job.job_id)}`);
        if (serial !== state.requestSerial) return;
        state.job = job;
        message("");
        renderJob();
      } catch (error) { if (serial === state.requestSerial) message(`Starea nu a putut fi actualizată: ${error.message} Reîncerc automat.`, true); }
      poll(serial);
    }, 1800);
  }
  byId("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isBusy()) return;
    const file = byId("video-file").files[0];
    if (!file) return;
    const limits = state.status && state.status.limits;
    if (limits && limits.max_upload_bytes && file.size > limits.max_upload_bytes) { message("Fișierul depășește limita de încărcare. Alege un clip mai scurt.", true); return; }
    if (limits && limits.max_duration_s && Number.isFinite(video.duration) && video.duration > limits.max_duration_s) { message(`Clipul depășește durata maximă de ${limits.max_duration_s} secunde. Decupează secvența relevantă.`, true); return; }
    try {
      const roi = readRoi();
      state.roi = roi;
      const form = new FormData();
      form.append("video", file);
      form.append("data_mode", byId("data-mode").value);
      form.append("operator", byId("operator").value.trim());
      form.append("fixed_camera_confirmed", byId("fixed-camera").checked ? "true" : "false");
      for (const [id, field] of [["source-url", "source_url"], ["attribution", "attribution"], ["license", "license"]]) {
        const value = byId(id).value.trim();
        if (value) form.append(field, value);
      }
      if (roi.length) form.append("roi_json", JSON.stringify(roi));
      state.submitting = true;
      setEditing(false);
      updateControls();
      message("Încărcare pe server… Păstrează această pagină deschisă.");
      const serial = ++state.requestSerial;
      state.job = await request(`${API}/jobs`, { method: "POST", body: form });
      state.submitting = false;
      message("");
      renderJob();
      const source = mediaUrl("source");
      if (video.getAttribute("src") !== source) { video.src = source; video.load(); }
      const url = new URL(window.location.href);
      url.searchParams.set("job", state.job.job_id);
      window.history.replaceState(null, "", url);
      poll(serial);
    } catch (error) { state.submitting = false; message(error.message, true); updateControls(); }
  });

  async function restoreJob() {
    const id = new URL(window.location.href).searchParams.get("job");
    if (!id) return;
    try {
      state.job = await request(`${API}/jobs/${encodeURIComponent(id)}`);
      state.roi = Array.isArray(state.job.roi) ? state.job.roi : [];
      if (state.job.operator) byId("operator").value = state.job.operator;
      byId("data-mode").value = state.job.data_mode;
      byId("fixed-camera").checked = Boolean(state.job.fixed_camera_confirmed);
      for (const [id, field] of [["source-url", "source_url"], ["attribution", "attribution"], ["license", "license"]]) byId(id).value = (state.job.provenance && state.job.provenance[field]) || "";
      byId("file-name").textContent = state.job.original_name || "Clipul analizei salvate";
      updateRoi();
      renderJob();
      byId("empty-video").classList.add("hidden");
      byId("video-wrap").classList.remove("hidden");
      video.src = mediaUrl("source");
      const serial = ++state.requestSerial;
      poll(serial);
    } catch (error) { message(`Analiza salvată nu a putut fi deschisă: ${error.message}`, true); }
  }
  void loadStatus();
  void restoreJob();
})();
