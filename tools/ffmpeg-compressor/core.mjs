export const DEFAULTS = Object.freeze({ target: 30, unit: 'MB', margin: 3.2, audio: 'keep', audioKbps: 96, resolution: '720', fps: 'source', preset: 'medium', platform: 'mac' });
const positive = (value, label) => {
  if (String(value).trim() === '') throw new Error(`${label}不可留空。`);
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${label}必須是大於零的數字。`);
  return number;
};
export function parseDuration(value) {
  const text = String(value).trim();
  if (!text) throw new Error('片長不可留空。');
  if (/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(text)) return positive(text, '片長');
  const match = /^(\d+):(\d{2}):(\d{2}(?:\.\d+)?)$/.exec(text);
  if (!match || +match[2] >= 60 || +match[3] >= 60) throw new Error('片長請填秒數或 HH:MM:SS，可含小數秒。');
  return positive(+match[1] * 3600 + +match[2] * 60 + +match[3], '片長');
}
export function normalizeSettings(input = {}) {
  const settings = { ...DEFAULTS, ...input };
  settings.target = positive(settings.target, '目標大小');
  if (!['MB','MiB'].includes(settings.unit)) throw new Error('請選擇 MB 或 MiB。');
  settings.targetBytes = Math.floor(settings.target * (settings.unit === 'MiB' ? 1048576 : 1000000));
  if (!Number.isSafeInteger(settings.targetBytes) || settings.targetBytes < 1) throw new Error('目標大小超出可計算範圍。');
  if (String(settings.margin).trim() === '') throw new Error('安全餘裕不可留空。');
  settings.margin = Number(settings.margin);
  if (!Number.isFinite(settings.margin) || settings.margin < 0 || settings.margin > 50) throw new Error('安全餘裕須介於 0–50%。');
  settings.ratio = (100 - settings.margin) / 100;
  if (!['keep','remove'].includes(settings.audio) || ![64,96,128,192].includes(Number(settings.audioKbps))) throw new Error('音訊設定無效。');
  settings.audioKbps = Number(settings.audioKbps);
  if (!['source','1080','720','480','360'].includes(settings.resolution)) throw new Error('解析度無效。');
  if (!['source','30','60'].includes(settings.fps)) throw new Error('FPS 無效。');
  if (!['veryfast','fast','medium','slow'].includes(settings.preset)) throw new Error('編碼 preset 無效。');
  if (!['mac','windows'].includes(settings.platform)) throw new Error('平台無效。');
  return settings;
}
export function estimate(settingsInput, seconds, audioState = 'unknown') {
  const settings = normalizeSettings(settingsInput);
  const duration = positive(seconds, '片長');
  if (!['unknown','yes','no'].includes(audioState)) throw new Error('音軌狀態無效。');
  const audioKbps = settings.audio === 'keep' && audioState !== 'no' ? settings.audioKbps : 0;
  const videoKbps = Math.floor((settings.targetBytes * settings.ratio * 8 / duration - audioKbps * 1000) / 1000);
  if (videoKbps < 16) throw new Error('目標太小：扣除音訊預算後，影片不足 16 kbps。請提高大小、降低音訊位元率或移除音訊。');
  return { seconds: duration, videoKbps, audioKbps, payloadBytes: (videoKbps + audioKbps) * 1000 * duration / 8, targetBytes: settings.targetBytes, uncertainAudio: settings.audio === 'keep' && audioState === 'unknown', lowQuality: videoKbps < 500 };
}
export function scaleDimensions(width, height, resolution = 'source') {
  if (!['source','1080','720','480','360'].includes(resolution)) throw new Error('解析度無效。');
  if (![width,height].every(value => Number.isFinite(value) && value >= 2)) throw new Error('來源寬高至少須為 2。');
  const short = resolution === 'source' ? Infinity : Number(resolution);
  const long = ({1080:1920,720:1280,480:854,360:640})[short] ?? Infinity;
  const ratio = Math.min(1, short / Math.min(width,height), long / Math.max(width,height));
  return { width: Math.max(2, Math.floor(width * ratio / 2) * 2), height: Math.max(2, Math.floor(height * ratio / 2) * 2) };
}
export function scaleFilter(resolution) {
  if (resolution === 'source') return "scale=w='max(2,trunc(iw/2)*2)':h='max(2,trunc(ih/2)*2)'";
  const long = ({1080:1920,720:1280,480:854,360:640})[resolution];
  if (!long) throw new Error('解析度無效。');
  const ratio = `min(1,min(${long}/max(iw,ih),${resolution}/min(iw,ih)))`;
  return `scale=w='max(2,trunc(iw*${ratio}/2)*2)':h='max(2,trunc(ih*${ratio}/2)*2)'`;
}
function safeText(value) {
  const text = String(value);
  if (/[\x00-\x1f\x7f]/.test(text)) throw new Error('路徑不可包含換行或控制字元。');
  return text;
}
export const quoteSh = value => "'" + safeText(value).replaceAll("'", "'\"'\"'") + "'";
export const quotePS = value => "'" + safeText(value).replace(/['\u2018\u2019\u201a\u201b]/g, character => character + character) + "'";
export function outputPath(input, settingsInput, custom = '') {
  const settings = normalizeSettings(settingsInput);
  if (custom.trim()) return safeText(custom);
  const value = safeText(input);
  const separator = settings.platform === 'windows' ? Math.max(value.lastIndexOf('/'),value.lastIndexOf('\\')) : value.lastIndexOf('/');
  const directory = value.slice(0,separator+1);
  const base = value.slice(separator+1);
  const dot = base.lastIndexOf('.');
  const stem = dot > 0 ? base.slice(0,dot) : base;
  return `${directory}${stem}_${settings.target}${settings.unit}.mp4`;
}
export function validateJobs(rows, settingsInput) {
  const settings = normalizeSettings(settingsInput);
  if (!rows.length) throw new Error('請至少加入一支影片。');
  const outputs = new Set();
  const canonical = value => settings.platform === 'windows' ? value.replaceAll('/','\\').toLowerCase() : value;
  const inputs = rows.map(row => canonical(String(row.path ?? '')));
  return rows.map((row,index) => {
    const input = safeText(String(row.path ?? ''));
    if (!input.trim()) throw new Error(`影片 ${index+1}：請填本機完整路徑或明確的相對路徑，檔名不會自動成為完整路徑。`);
    const output = outputPath(input,settings,row.output || '');
    if (!/\.mp4$/i.test(output)) throw new Error(`影片 ${index+1}：輸出副檔名須為 .mp4。`);
    if (settings.platform === 'windows' && /["<>|?*]/.test(input+output)) throw new Error('Windows 檔名不能包含雙引號、< > | ? *。請使用有效的本機路徑。');
    if (inputs.includes(canonical(output))) throw new Error('輸出不能是任一來源影片，原檔必須保留。');
    if (outputs.has(canonical(output))) throw new Error('批次影片的輸出路徑重複，請分別命名。');
    outputs.add(canonical(output));
    const seconds = String(row.duration ?? '').trim() ? parseDuration(row.duration) : null;
    const audioState = row.audioState || 'unknown';
    const budget = seconds ? estimate(settings,seconds,audioState) : null;
    return { input, output, seconds, audioState, budget };
  });
}
export function probeCommand(input, platform = 'mac') {
  const q = platform === 'windows' ? quotePS : quoteSh;
  return `${platform === 'windows' ? '& ' : ''}ffprobe -v error -show_entries format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate -of json -i ${q(input || '請替換為影片路徑')}`;
}
export function renderScript(template, rows, settingsInput) {
  const settings = normalizeSettings(settingsInput);
  const jobs = validateJobs(rows,settings);
  const q = settings.platform === 'windows' ? quotePS : quoteSh;
  const data = {
    TARGET_BYTES: String(settings.targetBytes), RATIO: String(settings.ratio),
    AUDIO_MODE: q(settings.audio), AUDIO_KBPS: String(settings.audioKbps), PRESET: q(settings.preset),
    FILTER: q(scaleFilter(settings.resolution)), FPS: q(settings.fps),
    JOBS: settings.platform === 'windows'
      ? jobs.map(job => `  @{ InputFile = ${q(job.input)}; OutputFile = ${q(job.output)}; ManualSeconds = ${job.seconds ?? 0} }`).join(',\n')
      : jobs.map(job => `if compress ${q(job.input)} ${q(job.output)} ${q(job.seconds ?? 0)}; then succeeded=$((succeeded+1)); else failed=$((failed+1)); fi`).join('\n')
  };
  return template.replace(/@@([A-Z_]+)@@/g,(_,key) => {
    if (!(key in data)) throw new Error(`未知腳本欄位：${key}`);
    return data[key];
  });
}
export function scriptFile(script, platform) {
  return { name: platform === 'windows' ? 'ff-tool.ps1' : 'ff-tool.sh', text: platform === 'windows' ? '\uFEFF'+script.replace(/\r?\n/g,'\r\n') : script };
}
