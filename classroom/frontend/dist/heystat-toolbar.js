/**
 * HeyStat Classroom Toolbar
 * Injected into Jamovi via Nginx sub_filter.
 * Floating corner widget (bottom-right) with Save / Download / Back buttons.
 */
(function () {
  'use strict';

  // Only show in the main Jamovi data editor, NOT in the
  // analysisui (/analyses/) or resultsview (/results/) iframes.
  if (/^\/(analyses|results)(\b|\/|$)/.test(window.location.pathname)) return;

  // Capture hs_file_id NOW, before Jamovi's SPA can wipe the query string
  // via history.replaceState/pushState during its initialization.
  const _query = new URLSearchParams(window.location.search);
  const _HS_FILE_ID = _query.get('hs_file_id');
  const _HS_ASSIGNMENT_ID = _query.get('hs_assignment_id');


  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function waitForEl(selector, cb, maxMs) {
    const start = Date.now();
    const iv = setInterval(() => {
      const el = document.querySelector(selector);
      if (el) { clearInterval(iv); cb(el); }
      else if (Date.now() - start > (maxMs || 15000)) clearInterval(iv);
    }, 300);
  }

  function getInstanceId() {
    const m = window.location.pathname.match(/\/([a-f0-9-]{8,})\//);
    return m ? m[1] : null;
  }

  function getTitle() {
    const el = document.querySelector('.header-file-name');
    const t = (el && el.textContent && el.textContent.trim()) || document.title || 'analysis';
    return t.replace(/[/\\?%*:|"<>]/g, '-').trim() || 'analysis';
  }

  /** The results jamovi rendered in this browser: the server writes no report into
   *  a saved .omv, so the LMS can only grade the tables it finds in these iframes. */
  function collectReport() {
    const chunks = [];
    document.querySelectorAll('div.jmv-results-container').forEach(function (box) {
      if (box.classList.contains('empty-analysis')) return;
      const frame = box.querySelector('iframe.analysis');
      const doc = frame && frame.contentDocument;
      if (!doc) return;
      let body = '';
      doc.querySelectorAll('h1, table').forEach(function (el) { body += el.outerHTML; });
      if (!body) return;
      const heading = doc.querySelector('h1') ? '' : '<h1>' + escapeHtml(box.getAttribute('data-analysis-name') || '') + '</h1>';
      chunks.push(heading + body);
    });
    return chunks.join('');
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  async function jamoviSaveToTemp() {
    const iid = getInstanceId();
    const base = iid ? `/${iid}` : '';
    const title = getTitle();
    const options = { path: `{{Temp}}/${title}.omv`, export: true };
    const fd = new FormData();
    fd.append('options', JSON.stringify(options));
    const resp = await fetch(`${base}/save`, { method: 'POST', body: fd });
    if (!resp.ok) throw new Error(`Save failed: ${resp.status}`);
    const text = await resp.text();
    const lines = text.trim().split('\n');
    const result = JSON.parse(lines[lines.length - 1]);
    if (result.status !== 'OK') throw new Error(result.message || 'Save error');
    return result;
  }

  function triggerBrowserDownload(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => document.body.removeChild(a), 1000);
  }

  function toast(msg, isError) {
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = `
      position:fixed; bottom:220px; right:20px; z-index:99999;
      background:${isError ? '#991B1B' : '#065F46'};
      color:#fff; padding:0.65rem 1.1rem; border-radius:8px;
      font-size:0.9rem; font-family:sans-serif; font-weight:600;
      box-shadow:0 4px 16px rgba(0,0,0,0.25); pointer-events:none;
      animation: hs-fadein 0.2s ease;
    `;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  async function downloadToDevice(btn) {
    btn.disabled = true;
      btn.textContent = '\u23f3 Đang xuất…';
    try {
      const result = await jamoviSaveToTemp();
      const iid = getInstanceId();
      const base = iid ? `/${iid}` : '';
      const source = result.filename || result.path.split('/').pop();
      const target = getTitle() + '.omv';
      const url = `${base}/dl/${source}?filename=${encodeURIComponent(target)}`;
      triggerBrowserDownload(url, target);
      toast('\u2713 Đã tải xong!');
    } catch (e) {
      toast('\u2717 L\u1ed7i: ' + e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = '\u2b07 Download';
    }
  }

  async function saveToAccount(btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3 Đang lưu…';
    try {
      const result = await jamoviSaveToTemp();
      const iid = getInstanceId();
      const base = iid ? `/${iid}` : '';
      const source = result.filename || result.path.split('/').pop();
      const target = getTitle() + '.omv';
      const downloadUrl = `${base}/dl/${source}?filename=${encodeURIComponent(target)}`;
      const fileResp = await fetch(downloadUrl);
      if (!fileResp.ok) throw new Error('Cannot fetch temp file');
      const blob = await fileResp.blob();
      const formData = new FormData();
      formData.append('file', blob, target);
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      // If opened from My Files, overwrite (PUT); otherwise create new (POST)
      const fileId = _HS_FILE_ID;
      let uploadResp;
      if (fileId) {
        uploadResp = await fetch(`/api/v1/files/${fileId}`, {
          method: 'PUT',
          headers,
          body: formData,
        });
      } else {
        uploadResp = await fetch('/api/v1/files', {
          method: 'POST',
          headers,
          body: formData,
        });
      }
      if (!uploadResp.ok) {
        const err = await uploadResp.json().catch(() => ({}));
        throw new Error(err.detail || `Upload failed: ${uploadResp.status}`);
      }
      toast('\u2713 Đã lưu vào Tệp của tôi!');
    } catch (e) {
      toast('\u2717 Lỗi: ' + e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = '\ud83d\udcbe Lưu file';
    }
  }

  async function syncToAssignment(btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3 Đang đồng bộ…';
    try {
      const result = await jamoviSaveToTemp();
      const iid = getInstanceId();
      const base = iid ? `/${iid}` : '';
      const source = result.filename || result.path.split('/').pop();
      const fileResp = await fetch(`${base}/dl/${source}`);
      if (!fileResp.ok) throw new Error('Không lấy được file .omv từ HeyStat');
      const blob = await fileResp.blob();

      const formData = new FormData();
      formData.append('assignment_id', _HS_ASSIGNMENT_ID);
      formData.append('file', blob, `${getTitle()}.omv`);
      const report = collectReport();
      if (report) formData.append('report', report);
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/v1/sessions/snapshot', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Đồng bộ thất bại: ${resp.status}`);
      }
      const data = await resp.json();
      toast(`\u2713 Đã đồng bộ ${(data.outputs || []).length} bảng kết quả`);
    } catch (e) {
      toast('\u2717 Lỗi: ' + e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = '\ud83d\udd04 Đồng bộ kết quả';
    }
  }

  function injectCSS() {
    const style = document.createElement('style');
    style.textContent = `
      .silky-bs-menu-item[data-op="save-item"],
      .silky-bs-menu-item[data-op="saveAs-item"] {
        display: none !important;
      }
      @keyframes hs-fadein {
        from { opacity:0; transform: translateY(8px); }
        to   { opacity:1; transform: translateY(0); }
      }
    `;
    document.head.appendChild(style);
  }

  function buildToolbar() {
    const bar = document.createElement('div');
    bar.id = 'hs-classroom-bar';
    bar.style.cssText = `
      position: fixed; bottom: 20px; right: 20px;
      display: flex; flex-direction: column; 
      align-items: flex-end; /* Căn các nút về phía bên phải */
      gap: 6px;
      z-index: 9999; 
      width: max-content; /* Độ rộng tự động theo nội dung nút */
      background: rgba(146,64,14,0.93); border-radius: 10px;
      padding: 10px; box-sizing: border-box;
      box-shadow: 0 4px 16px rgba(0,0,0,0.35);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      pointer-events: none;
    `;

    const btnStyle = `
      padding: 7px 10px; border: none; border-radius: 6px;
      cursor: pointer; font-size: 0.82rem; font-weight: 600;
      width: 100%; text-align: left; box-sizing: border-box;
      transition: opacity 0.15s;
      pointer-events: auto;
    `;

    const saveBtn = document.createElement('button');
    saveBtn.textContent = '\ud83d\udcbe L\u01b0u file';
    saveBtn.style.cssText = btnStyle + 'background:#FDE68A; color:#78350F;';
    saveBtn.onmouseenter = () => { saveBtn.style.opacity = '0.85'; };
    saveBtn.onmouseleave = () => { saveBtn.style.opacity = '1'; };
    saveBtn.onclick = () => saveToAccount(saveBtn);

    const dlBtn = document.createElement('button');
    dlBtn.textContent = '\u2b07 Download';
    dlBtn.style.cssText = btnStyle + 'background:rgba(255,255,255,0.18); color:#FEF3C7;';
    dlBtn.onmouseenter = () => { dlBtn.style.opacity = '0.85'; };
    dlBtn.onmouseleave = () => { dlBtn.style.opacity = '1'; };
    dlBtn.onclick = () => downloadToDevice(dlBtn);

    const backBtn = document.createElement('a');
    backBtn.href = '/classroom/';
    backBtn.textContent = '\u2190 L\u1edbp h\u1ecdc';
    backBtn.style.cssText = btnStyle + 'background:rgba(255,255,255,0.08); color:#FEF3C7; text-decoration:none; display:block;';
    backBtn.onmouseenter = () => { backBtn.style.opacity = '0.8'; };
    backBtn.onmouseleave = () => { backBtn.style.opacity = '1'; };

    bar.append(saveBtn, dlBtn, backBtn);

    if (_HS_ASSIGNMENT_ID) {
      const syncBtn = document.createElement('button');
      syncBtn.textContent = '\ud83d\udd04 Đồng bộ kết quả';
      syncBtn.style.cssText = btnStyle + 'background:#A7F3D0; color:#065F46;';
      syncBtn.onmouseenter = () => { syncBtn.style.opacity = '0.85'; };
      syncBtn.onmouseleave = () => { syncBtn.style.opacity = '1'; };
      syncBtn.onclick = () => syncToAssignment(syncBtn);
      bar.prepend(syncBtn);
    }

    document.body.appendChild(bar);
  }

  ready(function () {
    injectCSS();
    waitForEl('body', function () {
      buildToolbar();
    }, 5000);
  });
})();
