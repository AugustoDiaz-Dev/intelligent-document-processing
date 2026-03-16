// Simple config: use local API when running from localhost, otherwise use Render URL.
const API_BASE =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8001"
    : "https://intelligent-document-processing-qcbn.onrender.com";

const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const docIdEl = document.getElementById("doc-id");

function setStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`;
}

function formatCurrency(value) {
  if (value == null) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(Number(value));
  } catch {
    return String(value);
  }
}

function formatDate(value) {
  if (!value) return "—";
  try {
    const d = new Date(value);
    return d.toLocaleDateString();
  } catch {
    return String(value);
  }
}

function renderResult(doc) {
  docIdEl.textContent = doc.id ? doc.id.slice(0, 8) + "…" : "";

  const extraction = doc.extraction || {};
  const validations = doc.validations || [];
  const events = doc.events || [];

  const fieldConf = extraction.field_confidences || extraction.fieldConfidences || {};

  const confChip = (label, score) => {
    if (score == null) return "";
    const pct = Math.round(Number(score) * 100);
    return `<span class="chip">${label}: ${pct}%</span>`;
  };

  const validationChips = validations
    .map(
      (v) => `
      <span class="chip ${v.passed ? "pass" : "fail"}">
        ${v.rule_name} · ${Math.round(Number(v.score || 0) * 100)}%
      </span>`
    )
    .join("");

  const timeline = events
    .map(
      (e) => `
      <div class="timeline-item">
        <span class="dot"></span>
        <span class="timeline-step">${e.step}</span>
        <span class="timeline-meta">· ${e.status}${
          e.duration_ms != null ? ` · ${e.duration_ms}ms` : ""
        }</span>
      </div>`
    )
    .join("");

  resultEl.innerHTML = `
    <div class="result-grid">
      <div>
        <div class="field-label">Vendor</div>
        <div class="field-value">${extraction.vendor_name || "—"}</div>
      </div>
      <div>
        <div class="field-label">Invoice #</div>
        <div class="field-value">${extraction.invoice_number || "—"}</div>
      </div>
      <div>
        <div class="field-label">Total amount</div>
        <div class="field-value">${formatCurrency(extraction.total_amount)}</div>
      </div>
      <div>
        <div class="field-label">Tax ID</div>
        <div class="field-value">${extraction.tax_id || "—"}</div>
      </div>
      <div>
        <div class="field-label">Invoice date</div>
        <div class="field-value">${formatDate(extraction.invoice_date)}</div>
      </div>
      <div>
        <div class="field-label">Due date</div>
        <div class="field-value">${formatDate(extraction.due_date)}</div>
      </div>
    </div>

    <div class="chip-row">
      ${confChip("OCR", extraction.ocr_confidence)}
      ${confChip("Extraction", extraction.extraction_confidence)}
      ${confChip("Vendor", fieldConf.vendor_name)}
      ${confChip("Invoice #", fieldConf.invoice_number)}
      ${confChip("Total", fieldConf.total_amount)}
    </div>

    <div class="timeline">
      <div class="field-label">Validation rules</div>
      <div class="chip-row">
        ${validationChips || '<span class="muted">No validation rules executed.</span>'}
      </div>

      <div class="field-label" style="margin-top:10px;">Processing timeline</div>
      ${timeline || '<p class="muted">No processing events recorded.</p>'}
    </div>
  `;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    setStatus("Please choose a PDF file first.", "error");
    return;
  }

  setStatus("Uploading and processing…", "loading");

  try {
    const formData = new FormData();
    formData.append("file", file);

    const uploadResp = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      body: formData,
    });

    if (!uploadResp.ok) {
      const text = await uploadResp.text();
      throw new Error(`Upload failed: ${uploadResp.status} ${text}`);
    }

    const uploadData = await uploadResp.json();

    const detailResp = await fetch(`${API_BASE}/documents/${uploadData.document_id}`);
    if (!detailResp.ok) {
      const text = await detailResp.text();
      throw new Error(`Fetch failed: ${detailResp.status} ${text}`);
    }

    const doc = await detailResp.json();
    renderResult(doc);
    setStatus("Done. Extraction and validation complete.", "success");
  } catch (err) {
    console.error(err);
    setStatus("Something went wrong. Check the browser console for details.", "error");
  }
});

