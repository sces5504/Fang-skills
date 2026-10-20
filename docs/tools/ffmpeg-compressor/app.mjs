import { normalizeSettings, estimate, parseDuration, scaleDimensions, outputPath, validateJobs, renderScript, probeCommand, scriptFile } from './core.mjs';
const $ = id => document.getElementById(id);
let counter = 0;
const newJob = () => ({ id: ++counter, path: '', duration: '', audioState: 'unknown', output: '', info: '', width: null, height: null });
const jobs = [newJob()];
let mode = 'single';
let templates = null;
let templateError = '';
let renderedScript = '';
let toastTimer;
function settings() {
  return { target: $('target').value, unit: $('unit').value, margin: $('margin').value, resolution: $('resolution').value, fps: $('fps').value, preset: $('preset').value, audio: $('audio').value, audioKbps: $('audio-bitrate').value, platform: document.querySelector('[name="platform"]:checked').value };
}
const activeJobs = () => mode === 'single' ? jobs.slice(0,1) : jobs;
const formatBytes = bytes => `${(bytes / 1000000).toFixed(2)} MB / ${(bytes / 1048576).toFixed(2)} MiB`;
function toast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('visible'),4000);
}
function renderJobs() {
  $('jobs').replaceChildren();
  for (const [index,job] of activeJobs().entries()) {
    const card = document.createElement('div');
    card.className = 'job';
    card.dataset.id = job.id;
    card.innerHTML = `<div class="job-heading"><strong>影片 ${index+1}</strong><button type="button" class="remove-job" aria-label="移除影片 ${index+1}">移除</button></div><p class="file-info"></p><div class="field"><label for="path-${job.id}">本機影片路徑</label><input id="path-${job.id}" class="path" type="text" autocomplete="off" spellcheck="false" placeholder="完整路徑，或相對目前工作資料夾的路徑"></div><p class="hint">直接填路徑，不需自行加引號；相對路徑以執行時的工作資料夾為準。</p><div class="two-fields"><div class="field"><label for="duration-${job.id}">片長（秒或 HH:MM:SS）</label><input id="duration-${job.id}" class="duration" type="text" inputmode="text" placeholder="留空，由 ffprobe 實測"></div><div class="field"><label for="audio-state-${job.id}">來源音軌</label><select id="audio-state-${job.id}" class="audio-state"><option value="unknown">未知（先預留音訊）</option><option value="yes">有音軌</option><option value="no">無音軌</option></select></div></div><div class="field"><label for="output-${job.id}">輸出路徑／檔名 <small>選填</small></label><input id="output-${job.id}" class="output" type="text" autocomplete="off" spellcheck="false"><p class="hint output-hint"></p></div><div class="budget" role="status"></div>`;
    for (const [selector,key] of [['.path','path'],['.duration','duration'],['.audio-state','audioState'],['.output','output']]) {
      const input = card.querySelector(selector);
      input.value = job[key];
      input.addEventListener(input.tagName === 'SELECT' ? 'change' : 'input', () => { job[key] = input.value; renderResults(); });
    }
    const remove = card.querySelector('.remove-job');
    remove.hidden = mode === 'single' || jobs.length === 1;
    remove.addEventListener('click', () => { jobs.splice(jobs.indexOf(job),1); renderJobs(); });
    $('jobs').append(card);
  }
  $('add-job').hidden = mode !== 'batch';
  renderResults();
}
function renderResults() {
  const config = settings();
  const windows = config.platform === 'windows';
  $('audio-bitrate').disabled = config.audio === 'remove';
  $('download-script').textContent = windows ? '下載 .ps1' : '下載 .sh';
  $('run-help').textContent = windows
    ? 'Windows：在下載資料夾開啟 PowerShell，執行 & .\\ff-tool.ps1。下載檔為 UTF-8 BOM，支援中文路徑。若執行原則阻擋，請依組織政策允許此腳本，或在檢查內容後將完整腳本貼到 PowerShell；不用永久變更全系統設定。'
    : 'macOS：在下載資料夾開啟終端機，執行 bash ./ff-tool.sh。也可將完整腳本貼到 zsh / bash。';
  document.querySelectorAll('[data-size]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.size === config.target)));
  for (const job of activeJobs()) {
    const card = document.querySelector(`.job[data-id="${job.id}"]`);
    card.querySelector('.file-info').textContent = job.info;
    const budget = card.querySelector('.budget');
    budget.className = 'budget';
    const hint = card.querySelector('.output-hint');
    try {
      normalizeSettings(config);
      const output = job.path.trim() ? outputPath(job.path,config,job.output) : '';
      card.querySelector('.output').placeholder = output || '預設與來源同資料夾，檔名加 _30MB.mp4';
      hint.textContent = output ? `預計輸出：${output}` : '不覆寫原檔與任何既有輸出檔。';
      if (!job.duration.trim()) {
        budget.textContent = '尚無片長估算；腳本會先用 ffprobe 確認片長與音軌，再計算位元率。';
      } else {
        const result = estimate(config,parseDuration(job.duration),job.audioState);
        budget.replaceChildren();
        const title = document.createElement('strong');
        title.textContent = `影片 ${result.videoKbps} kbps · 音訊 ${result.audioKbps} kbps`;
        budget.append(title, document.createElement('br'), `估計媒體資料 ${formatBytes(result.payloadBytes)}（未含容器）`);
        if (result.uncertainAudio) budget.append(document.createElement('br'),'音軌未知：先保守預留；腳本會按實際來源重算。');
        if (result.lowQuality) { budget.classList.add('warning'); budget.append(document.createElement('br'),'位元率偏低，動態畫面可能明顯失真；建議 480p / 360p，或增加目標大小。'); }
      }
      if (job.width && job.height) {
        const scaled = scaleDimensions(job.width,job.height,config.resolution);
        budget.append(document.createElement('br'),`尺寸 ${job.width}×${job.height} → ${scaled.width}×${scaled.height}`);
      }
    } catch (error) { budget.classList.add('error'); budget.textContent = error.message; }
  }
  try {
    $('probe').value = activeJobs().map(job => probeCommand(job.path,config.platform)).join('\n\n');
  } catch (error) { $('probe').value = error.message; }
  try {
    if (templateError) throw new Error(templateError);
    if (!templates) throw new Error('正在載入腳本範本…');
    validateJobs(activeJobs(),config);
    renderedScript = renderScript(windows ? templates.windows : templates.mac,activeJobs(),config);
    $('script').value = renderedScript;
    $('form-error').textContent = '';
    $('copy-script').disabled = false;
    $('download-script').disabled = false;
    $('script-note').textContent = `${activeJobs().length} 支影片 · two-pass · libx264 / yuv420p / faststart。執行時偵測真實片長與音軌，各工作獨立暫存，原始影片與既有輸出不覆寫。估計不保證低於上限，完成後會檢查實際 bytes。`;
  } catch (error) {
    renderedScript = '';
    $('script').value = '';
    $('copy-script').disabled = true;
    $('download-script').disabled = true;
    $('form-error').textContent = activeJobs().every(job => !job.path.trim()) && !templateError ? '' : error.message;
    $('script-note').textContent = '填入有效的來源路徑與設定後即可產生腳本。片長可留空，執行時偵測。';
  }
}
function readFileMetadata(file,job) {
  job.info = `${file.name} · ${formatBytes(file.size)} · 正在讀取本機資訊…（仍須填入路徑）`;
  renderResults();
  const video = document.createElement('video');
  video.preload = 'metadata';
  const url = URL.createObjectURL(file);
  let finished = false;
  function finish(success) {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    if (success && Number.isFinite(video.duration) && video.duration > 0) {
      if (!job.duration.trim()) job.duration = String(Math.round(video.duration * 1000) / 1000);
      job.width = video.videoWidth; job.height = video.videoHeight;
      job.info = `${file.name} · ${formatBytes(file.size)} · ${video.duration.toFixed(3)} 秒 · ${job.width}×${job.height} · 音軌仍需確認`;
    } else job.info = `${file.name} · ${formatBytes(file.size)} · 瀏覽器無法讀取資訊，請手動填寫或交給腳本偵測。`;
    video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url);
    if (activeJobs().includes(job)) {
      document.getElementById(`duration-${job.id}`).value = job.duration;
      renderResults();
    }
  }
  const timer = setTimeout(() => finish(false),15000);
  video.onloadedmetadata = () => finish(true);
  video.onerror = () => finish(false);
  video.src = url;
}
function addFiles(files) {
  const selected = Array.from(files);
  if (!selected.length) return;
  const targets = [];
  for (const file of selected) {
    const empty = jobs.find(job => !job.path && !job.duration && !job.info);
    const job = empty || newJob();
    if (!empty) jobs.push(job);
    job.info = file.name;
    targets.push([file,job]);
  }
  if (jobs.length > 1) { mode = 'batch'; document.querySelector('[name="mode"][value="batch"]').checked = true; }
  renderJobs();
  targets.forEach(([file,job]) => readFileMetadata(file,job));
}
for (const input of document.querySelectorAll('[name="mode"]')) input.addEventListener('change',() => { mode = input.value; renderJobs(); });
for (const input of document.querySelectorAll('.settings input,.settings select')) input.addEventListener(input.tagName === 'SELECT' || input.type === 'radio' ? 'change' : 'input',renderResults);
for (const button of document.querySelectorAll('[data-size]')) button.addEventListener('click',() => { $('target').value = button.dataset.size; renderResults(); });
$('add-job').addEventListener('click',() => { jobs.push(newJob()); renderJobs(); document.getElementById(`path-${jobs.at(-1).id}`).focus(); });
$('examples').addEventListener('click',() => {
  const names = ['雷電 II 攻略.mp4','雷電系列介紹.mp4','Ikaruga is a Masterpiece.mp4'];
  const seconds = [974,532,652];
  jobs.splice(0,jobs.length,...names.map((name,i) => ({...newJob(),path:`./${name}`,duration:String(seconds[i]),audioState:'no',info:'範例相對路徑，請換成你的實際影片位置。'})));
  mode = 'batch'; document.querySelector('[name="mode"][value="batch"]').checked = true;
  $('audio').value = 'remove'; renderJobs();
});
$('files').addEventListener('change',() => { addFiles($('files').files); $('files').value=''; });
for (const type of ['dragenter','dragover']) $('drop-zone').addEventListener(type,event => { event.preventDefault(); $('drop-zone').classList.add('dragging'); });
for (const type of ['dragleave','drop']) $('drop-zone').addEventListener(type,event => { event.preventDefault(); $('drop-zone').classList.remove('dragging'); if (type === 'drop') addFiles(event.dataTransfer.files); });
async function copy(text,element) {
  try { await navigator.clipboard.writeText(text); toast('已複製，請先檢查路徑，再到自己的終端機執行。'); }
  catch { element.focus(); element.select(); toast('文字已選取，請手動複製。'); }
}
$('copy-script').addEventListener('click',() => copy(renderedScript,$('script')));
$('copy-probe').addEventListener('click',() => copy($('probe').value,$('probe')));
$('download-script').addEventListener('click',() => {
  const file = scriptFile(renderedScript,settings().platform);
  const url = URL.createObjectURL(new Blob([file.text],{type:'text/plain;charset=utf-8'}));
  const link = document.createElement('a'); link.href=url; link.download=file.name; link.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
});
renderJobs();
Promise.all(['templates/bash.txt','templates/powershell.txt'].map(async path => {
  const response = await fetch(new URL(path,import.meta.url));
  if (!response.ok) throw new Error('範本載入失敗，請重新整理頁面；無法離線載入尚未快取的資源。');
  return response.text();
})).then(([mac,windows]) => { templates={mac,windows}; renderResults(); }).catch(error => { templateError=error.message; renderResults(); });
