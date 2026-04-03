import type { Task } from '../types';

function hhmm(iso: string): string {
  return iso.substring(11, 16);
}

function staffingBadge(task: Task): string {
  if (task.is_fully_staffed) {
    return `<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">
              ${task.assigned_people}/${task.required_people} ✓
            </span>`;
  }
  if (task.assigned_people > 0) {
    return `<span style="background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">
              ${task.assigned_people}/${task.required_people} ⚠
            </span>`;
  }
  return `<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">
            ${task.assigned_people}/${task.required_people} ✗
          </span>`;
}

export interface PrintScheduleOptions {
  title: string;
  date: string;           // yyyy-MM-dd
  formattedDate: string;  // ex : "2 avril 2026"
  tasks: Task[];
  conflictIds?: Set<number>;
  subtitle?: string;      // ex : nom de l'employé
}

export function printSchedule(opts: PrintScheduleOptions): void {
  const { title, formattedDate, tasks, conflictIds, subtitle } = opts;

  const taskRows = tasks.length === 0
    ? `<tr><td colspan="5" style="text-align:center;color:#6b7280;padding:24px;">Aucune tâche ce jour.</td></tr>`
    : tasks.map((task) => {
        const isConflict = conflictIds?.has(task.id) ?? false;
        const rowBg = isConflict ? '#fff5f5' : 'transparent';
        const conflictCell = conflictIds !== undefined
          ? `<td style="text-align:center;">${isConflict ? '<span style="color:#dc2626;font-weight:700;">⚠ Conflit</span>' : ''}</td>`
          : '';

        return `
          <tr style="background:${rowBg};border-bottom:1px solid #e5e7eb;">
            <td style="padding:10px 12px;font-weight:600;">${hhmm(task.start_at)} – ${hhmm(task.end_at)}</td>
            <td style="padding:10px 12px;">${task.title}</td>
            <td style="padding:10px 12px;color:#6b7280;font-size:13px;">${task.description ?? '—'}</td>
            <td style="padding:10px 12px;color:#374151;font-size:13px;">
              ${task.assigned_users.length > 0 ? task.assigned_users.map((user) => user.name).join(', ') : 'Aucun'}
            </td>
            ${conflictIds !== undefined
              ? conflictCell
              : `<td style="padding:10px 12px;text-align:center;">${staffingBadge(task)}</td>`}
          </tr>`;
      }).join('');

  const hasConflictCol = conflictIds !== undefined;
  const extraHeader = hasConflictCol
    ? '<th style="text-align:center;">Statut</th>'
    : '<th style="text-align:center;">Effectif</th>';

  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>${title} — ${formattedDate}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      color: #111827;
      padding: 32px;
      background: #fff;
    }
    .header {
      border-bottom: 2px solid #4f46e5;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    .header h1 {
      font-size: 22px;
      font-weight: 700;
      color: #4f46e5;
    }
    .header .meta {
      display: flex;
      gap: 24px;
      margin-top: 6px;
      color: #6b7280;
      font-size: 13px;
    }
    .summary {
      display: flex;
      gap: 20px;
      margin-bottom: 20px;
    }
    .pill {
      padding: 6px 16px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
    }
    .pill-total   { background: #ede9fe; color: #5b21b6; }
    .pill-full    { background: #dcfce7; color: #166534; }
    .pill-partial { background: #fef9c3; color: #854d0e; }
    .pill-empty   { background: #fee2e2; color: #991b1b; }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    thead tr {
      background: #f3f4f6;
    }
    th {
      padding: 10px 12px;
      text-align: left;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      color: #6b7280;
      letter-spacing: 0.04em;
    }
    td { vertical-align: middle; }
    tr:last-child { border-bottom: none; }
    .footer {
      margin-top: 32px;
      font-size: 11px;
      color: #9ca3af;
      text-align: right;
      border-top: 1px solid #e5e7eb;
      padding-top: 10px;
    }
    @media print {
      body { padding: 16px; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>📅 ${title}</h1>
    <div class="meta">
      <span><strong>Date :</strong> ${formattedDate}</span>
      ${subtitle ? `<span><strong>Employé :</strong> ${subtitle}</span>` : ''}
      <span><strong>Tâches :</strong> ${tasks.length}</span>
    </div>
  </div>

  ${!hasConflictCol ? `
  <div class="summary">
    <span class="pill pill-total">${tasks.length} tâche${tasks.length !== 1 ? 's' : ''}</span>
    <span class="pill pill-full">${tasks.filter(t => t.is_fully_staffed).length} complètes</span>
    <span class="pill pill-partial">${tasks.filter(t => !t.is_fully_staffed && t.assigned_people > 0).length} partielles</span>
    <span class="pill pill-empty">${tasks.filter(t => t.assigned_people === 0).length} sans personne</span>
  </div>` : ''}

  <table>
    <thead>
      <tr>
        <th style="width:130px;">Horaire</th>
        <th>Tâche</th>
        <th>Description</th>
        <th>Affectés</th>
        ${extraHeader}
      </tr>
    </thead>
    <tbody>
      ${taskRows}
    </tbody>
  </table>

  <div class="footer">
    Généré le ${new Date().toLocaleString('fr-FR')} — Team Scheduler
  </div>
</body>
</html>`;

  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) return;
  win.document.write(html);
  win.document.close();
  win.focus();
  // Délai pour laisser le navigateur rendre le contenu avant l'impression
  setTimeout(() => {
    win.print();
  }, 300);
}
