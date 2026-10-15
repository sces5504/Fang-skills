export const REPOSITORY = 'https://github.com/sces5504/Fang-skills';
export function buildPrompt({ skill, ref = 'main', task = '' }) {
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(skill)) throw new Error('請選擇有效的技能。');
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/.test(ref) || ref.includes('..') || ref.includes('//') || ref.endsWith('/')) throw new Error('版本只能使用 branch、tag 或 commit，不含空白。');
  const assignment = task.trim() || `請依照 ${skill} 的流程，處理目前專案中適用的工作。`;
  return `請從 ${REPOSITORY} 取得版本「${ref}」的 skills/${skill}/ 完整資料夾，存到目前專案之外的暫存目錄，並記錄實際來源 commit。若只有單一檔案，也必須確認沒有遺漏必要資源。\n\n先完整閱讀 SKILL.md，再依需要讀取其參考文件、檢查腳本用途，按照技能流程執行以下任務：\n\n${assignment}\n\n不要把技能安裝或複製進目前專案，不要修改 AGENTS.md 或其他全專案指令，也不要指派或干涉其他 AI。遵守技能的修改範圍，保留使用者尚未提交的變更；若任務需要超出範圍，先說明限制。\n\n若無法取得指定版本的完整技能，請說明原因並停止，不要靜默改用其他版本、憑記憶模擬或假裝已載入。完成後以繁體中文簡潔回報修改、實際驗證結果及限制。未經我另外要求，不要自動提交、推送或部署。`;
}
export function parseSkills(entries) {
  if (!Array.isArray(entries)) throw new Error('技能目錄回應無效。');
  return entries.filter(item => item.type === 'dir' && /^[a-z0-9][a-z0-9-]{0,63}$/.test(item.name))
    .map(item => item.name).sort((a, b) => a.localeCompare(b));
}
