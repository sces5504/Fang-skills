import { buildPrompt, parseSkills, REPOSITORY } from './prompt.mjs';
const $ = id => document.getElementById(id);
const presets = {
  full: '請改善目前專案的 README 文案、排版、橫幅與徽章，以及 GitHub Pages 社群分享預覽。先理解專案內容，維持專業成熟的呈現。',
  readme: '只整理目前專案的 README：改善文案、排版、橫幅與徽章，呈現成熟專業的 GitHub 專案門面。這次不處理網站的社群 metadata。',
  social: '只改善目前 GitHub Pages 網站的社群分享標題、描述、封面圖片與 metadata。這次不要讀取或修改 README。'
};
let lastSynced = 0;
let syncing = false;
let descriptionRequest = 0;
let catalogRequest = 0;
let toastTimer;
const initialSkill = new URLSearchParams(location.search).get('skill');
function render() {
  try {
    const text = buildPrompt({ skill: $('skill').value, ref: $('version').value.trim() || 'main', task: $('task').value });
    $('output').value = text;
    $('output-error').textContent = '';
    $('copy').disabled = false;
    $('prompt-size').textContent = `${text.length.toLocaleString()} 字元 · 直接貼到 Codex`;
    $('version').removeAttribute('aria-invalid');
  } catch (error) {
    $('output').value = '';
    $('output-error').textContent = error.message;
    $('copy').disabled = true;
    $('version').setAttribute('aria-invalid', 'true');
  }
}
async function showSkill() {
  const request = ++descriptionRequest;
  const skill = $('skill').value;
  const ref = $('version').value.trim() || 'main';
  $('skill-name').textContent = skill;
  $('skill-source').href = `${REPOSITORY}/tree/${encodeURIComponent(ref)}/skills/${encodeURIComponent(skill)}`;
  $('skill-description').textContent = skill === 'polisher' ? '整理 README 的文案、橫幅與徽章，改善 GitHub Pages 分享預覽。' : '從中央 repo 取得這個技能的完整工作流程。';
  document.querySelector('.presets').hidden = skill !== 'polisher';
  if (skill === 'polisher') return;
  try {
    const response = await fetch(`https://raw.githubusercontent.com/sces5504/Fang-skills/${encodeURIComponent(ref)}/skills/${encodeURIComponent(skill)}/SKILL.md`, { signal: AbortSignal.timeout(10000) });
    if (!response.ok) return;
    const content = await response.text();
    const description = content.match(/^---\s*\n[\s\S]*?^description:\s*(.+)$/m)?.[1]?.trim().replace(/^['"]|['"]$/g, '');
    if (request === descriptionRequest && description && !['>', '|', '>-', '|-'].includes(description)) $('skill-description').textContent = description;
  } catch { /* The canonical source link remains available without a description. */ }
}
async function syncCatalog() {
  const ref = $('version').value.trim() || 'main';
  try { buildPrompt({ skill: 'polisher', ref }); } catch { return; }
  const request = ++catalogRequest;
  syncing = true;
  $('refresh').disabled = true;
  $('sync-status').textContent = '正在同步技能目錄…';
  try {
    const response = await fetch(`https://api.github.com/repos/sces5504/Fang-skills/contents/skills?ref=${encodeURIComponent(ref)}`, { cache: 'no-store', signal: AbortSignal.timeout(12000) });
    if (!response.ok) throw new Error('無法取得技能目錄');
    const skills = parseSkills(await response.json());
    if (request !== catalogRequest) return;
    if (!skills.length) throw new Error('這個版本沒有可用技能');
    const previous = $('skill').value;
    $('skill').replaceChildren(...skills.map(name => new Option(name, name)));
    $('skill').value = skills.includes(previous) ? previous : skills[0];
    if (!lastSynced && initialSkill && skills.includes(initialSkill)) $('skill').value = initialSkill;
    if ($('skill').value !== previous) $('task').value = $('skill').value === 'polisher' ? presets.full : '';
    lastSynced = Date.now();
    $('sync-status').textContent = `${skills.length} 個技能 · 已同步 ${new Date(lastSynced).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}`;
    showSkill();
    render();
  } catch {
    if (request === catalogRequest) $('sync-status').textContent = '暫時無法同步，保留目前清單。可稍後再試；請確認技能存在於指定版本。';
  } finally {
    if (request === catalogRequest) { syncing = false; $('refresh').disabled = false; }
  }
}
$('prompt-form').addEventListener('submit', event => event.preventDefault());
$('task').addEventListener('input', () => {
  document.querySelectorAll('[data-preset]').forEach(button => button.setAttribute('aria-pressed', String($('task').value === presets[button.dataset.preset])));
  render();
});
$('version').addEventListener('input', render);
$('version').addEventListener('change', syncCatalog);
$('skill').addEventListener('change', () => {
  $('task').value = $('skill').value === 'polisher' ? presets.full : '';
  showSkill();
  render();
});
$('refresh').addEventListener('click', syncCatalog);
for (const button of document.querySelectorAll('[data-preset]')) {
  button.setAttribute('aria-pressed', String(button.dataset.preset === 'full'));
  button.addEventListener('click', () => {
    $('task').value = presets[button.dataset.preset];
    document.querySelectorAll('[data-preset]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    render();
  });
}
$('copy').addEventListener('click', async () => {
  let message = '已複製，貼到目標專案的 Codex 即可。';
  try { await navigator.clipboard.writeText($('output').value); }
  catch {
    $('output').focus();
    $('output').select();
    message = '文字已選取，請手動複製。';
  }
  $('toast').textContent = message;
  $('toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 3500);
});
document.addEventListener('visibilitychange', () => { if (!document.hidden && !syncing && Date.now() - lastSynced > 60000) syncCatalog(); });
setInterval(() => { if (!document.hidden && !syncing) syncCatalog(); }, 300000);
render();
syncCatalog();
