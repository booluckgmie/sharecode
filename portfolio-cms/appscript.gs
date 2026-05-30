// ═══════════════════════════════════════════════════════════════
//  PROJECT HUB — Google Apps Script
//
//  HOW TO USE:
//  1. Paste this entire file into Apps Script (Extensions → Apps Script)
//  2. Click Save, then Run → setupSheets  (creates tabs + loads data)
//  3. Deploy → New deployment → Web app
//       Execute as : Me
//       Who has access : Anyone
//  4. Copy the /exec URL → paste into your hub's "Connect Sheet" dialog
// ═══════════════════════════════════════════════════════════════

const GROUPS_SHEET = 'groups';
const CARDS_SHEET  = 'cards';

// ── MAIN ENDPOINT ─────────────────────────────────────────────
// Supports both plain JSON and JSONP (?callback=fnName)
// JSONP is used by the hub page to bypass CORS redirect issues.
function doGet(e) {
  try {
    const ss     = SpreadsheetApp.getActiveSpreadsheet();
    const groups = readGroups(ss);
    const cards  = readCards(ss);

    const payload = {
      groups:  groups,
      cards:   cards,
      _synced: new Date().toISOString(),
      _source: 'google-sheets',
      _count:  cards.length
    };

    const json = JSON.stringify(payload);

    // JSONP mode — wrap in callback fn if ?callback= is present
    const cb = (e && e.parameter && e.parameter.callback) ? e.parameter.callback : null;
    if (cb) {
      const safeCb = cb.replace(/[^a-zA-Z0-9_]/g, '');
      return ContentService
        .createTextOutput(safeCb + '(' + json + ')')
        .setMimeType(ContentService.MimeType.JAVASCRIPT);
    }

    // Plain JSON mode
    return ContentService
      .createTextOutput(json)
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    const errJson = JSON.stringify({ error: err.message });
    const cb = (e && e.parameter && e.parameter.callback) ? e.parameter.callback.replace(/[^a-zA-Z0-9_]/g,'') : null;
    if (cb) {
      return ContentService.createTextOutput(cb + '(' + errJson + ')').setMimeType(ContentService.MimeType.JAVASCRIPT);
    }
    return ContentService.createTextOutput(errJson).setMimeType(ContentService.MimeType.JSON);
  }
}

// ── READ GROUPS ───────────────────────────────────────────────
function readGroups(ss) {
  const sheet = ss.getSheetByName(GROUPS_SHEET);
  if (!sheet) return [];
  const rows    = sheet.getDataRange().getValues();
  const headers = rows[0].map(h => h.toString().trim().toLowerCase());
  const groups  = [];

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const obj = {};
    headers.forEach((h, j) => { obj[h] = (row[j] !== undefined && row[j] !== null) ? row[j].toString().trim() : ''; });
    if (!obj.id || !obj.label) continue;
    groups.push({
      id:    obj.id,
      label: obj.label,
      icon:  obj.icon  || 'folder',
      color: obj.color || '#4f7cff'
    });
  }
  return groups;
}

// ── READ CARDS ────────────────────────────────────────────────
function readCards(ss) {
  const sheet = ss.getSheetByName(CARDS_SHEET);
  if (!sheet) return [];
  const rows    = sheet.getDataRange().getValues();
  const headers = rows[0].map(h => h.toString().trim().toLowerCase());
  const cards   = [];

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const obj = {};
    headers.forEach((h, j) => { obj[h] = (row[j] !== undefined && row[j] !== null) ? row[j].toString().trim() : ''; });
    if (!obj.url || !obj.title) continue;

    cards.push({
      id:       obj.id       || ('c_' + (i + 1)),
      group:    obj.group    || 'dev',
      url:      obj.url,
      title:    obj.title,
      tag:      obj.tag      || '',
      desc:     obj.desc     || '',
      size:     obj.size     || '',
      color:    obj.color    || '#4f7cff',
      thumbUrl: obj.thumburl || '',
      faded:    (obj.faded  === 'TRUE' || obj.faded  === 'true'  || obj.faded  === '1'),
      newTab:   (obj.newtab === 'TRUE' || obj.newtab === 'true'  || obj.newtab === '1')
    });
  }
  return cards;
}

// ═══════════════════════════════════════════════════════════════
//  SETUP — Run this ONCE from the editor:  Run → setupSheets
//  Creates the two sheets and pre-loads all 18 existing projects.
// ═══════════════════════════════════════════════════════════════
function setupSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // ── groups sheet ──────────────────────────────────────────
  let gs = ss.getSheetByName(GROUPS_SHEET);
  if (!gs) gs = ss.insertSheet(GROUPS_SHEET);
  gs.clearContents();
  gs.clearFormats();

  const gHeaders = ['id', 'label', 'icon', 'color'];
  gs.getRange(1, 1, 1, gHeaders.length)
    .setValues([gHeaders])
    .setFontWeight('bold')
    .setBackground('#1a1e28')
    .setFontColor('#e8e9ed');

  const groupRows = [
    ['gov',  'Government & Regulatory', 'building-bank',      '#4c9be8'],
    ['ngo',  'NGO & Social Impact',     'heart-handshake',    '#69db7c'],
    ['corp', 'Corporate & Governance',  'building-community', '#4f7cff'],
    ['fin',  'Finance & Fintech',       'chart-line',         '#ffd43b'],
    ['hr',   'HR & Talent',             'users',              '#b39ddb'],
    ['data', 'Data & Analytics',        'chart-dots-3',       '#ffa94d'],
    ['dev',  'Dev & Engineering',       'code',               '#4dd0e1'],
    ['comm', 'Comms & Marketing',       'speakerphone',       '#f06292'],
  ];
  gs.getRange(2, 1, groupRows.length, gHeaders.length).setValues(groupRows);
  gs.setColumnWidths(1, gHeaders.length, 200);
  gs.setFrozenRows(1);

  // ── cards sheet ───────────────────────────────────────────
  let cs = ss.getSheetByName(CARDS_SHEET);
  if (!cs) cs = ss.insertSheet(CARDS_SHEET);
  cs.clearContents();
  cs.clearFormats();

  const cHeaders = ['id', 'group', 'url', 'title', 'tag', 'desc', 'size', 'color', 'thumbUrl', 'faded', 'newTab'];
  cs.getRange(1, 1, 1, cHeaders.length)
    .setValues([cHeaders])
    .setFontWeight('bold')
    .setBackground('#1a1e28')
    .setFontColor('#e8e9ed');

  const cardRows = [
    ['c1',  'corp', 'shareholder_network.html',  'Shareholder Network',        'Network',      'Force-graph visualisation of shareholder–company relationships.',          '189 KB', '#4f7cff', '', 'FALSE', 'FALSE'],
    ['c2',  'corp', 'shareholder_coi6.html',     'COI Dashboard v6',           'COI v6',       'Conflict-of-interest declaration dashboard.',                              '22 KB',  '#4f7cff', '', 'FALSE', 'FALSE'],
    ['c3',  'corp', 'coi_v1.html',               'Shareholder–Company Vis',    'Shareholders', 'Original index — shareholder list and network.',                           '',       '#4f7cff', '', 'FALSE', 'FALSE'],
    ['c4',  'corp', 'shareholder_db2.csv',        'Shareholder Database',       'Data',         'Raw CSV dataset — shareholder records and affiliations.',                  '72 KB',  '#4f7cff', '', 'FALSE', 'TRUE'],
    ['c5',  'corp', 'shareholder_coi6_old.html', 'COI Dashboard (legacy)',     'Archive',      'Previous COI dashboard version — kept for reference.',                    '17 KB',  '#4f7cff', '', 'TRUE',  'FALSE'],
    ['c6',  'hr',   'vistatalent.html',           'VistaTalent',                'Talent',       'Full-featured HR talent dashboard — profiles, org chart, performance.',    '44 KB',  '#b39ddb', '', 'FALSE', 'FALSE'],
    ['c7',  'hr',   'vistatalent-mini.html',      'VistaTalent Mini',           'Compact',      'Lightweight compact version for embedding or quick lookup.',               '35 KB',  '#b39ddb', '', 'FALSE', 'FALSE'],
    ['c8',  'fin',  'paydaylock.html',            'PaydayLock',                 'Payroll',      'Payroll lock and sign-off — freeze periods, confirm cut-offs.',            '11 KB',  '#ffd43b', '', 'FALSE', 'FALSE'],
    ['c9',  'fin',  'ogsedash.html',              'OGSE Dashboard',             'KPI',          'OGS/E financial metrics — KPI cards, trend charts, period comparison.',   '18 KB',  '#ffd43b', '', 'FALSE', 'FALSE'],
    ['c10', 'data', 'samuraiv2_opdash.html',      'Samurai v2 — Ops',          'Ops',          'Operations command dashboard — status tiles, activity log, KPI summary.', '22 KB',  '#ffa94d', '', 'FALSE', 'FALSE'],
    ['c11', 'data', 'samuraiv2_opdash-int.html',  'Samurai v2 — Interactive',   'Interactive',  'Enhanced interactive build — drill-down filters, live panels, alerts.',   '27 KB',  '#ffa94d', '', 'FALSE', 'FALSE'],
    ['c12', 'data', 'weather_indc.html',          'Weather Indicator',          'Weather',      'Field operations weather widget — conditions, forecast, work-safe.',       '24 KB',  '#ffa94d', '', 'FALSE', 'FALSE'],
    ['c13', 'dev',  'nexaflow.html',              'NexaFlow',                   'Workflow',     'Visual workflow builder — node-based automation with branching.',          '47 KB',  '#4dd0e1', '', 'FALSE', 'FALSE'],
    ['c14', 'dev',  'pyjourney.html',             'PyJourney',                  'Learning',     'Python learning tracker — progress, snippets, and milestone badges.',      '31 KB',  '#4dd0e1', '', 'FALSE', 'FALSE'],
    ['c15', 'dev',  'searchswec.html',            'SearchSWEC',                 'Search',       'Full-featured local search — indexed dataset, faceted filters.',           '1.2 MB', '#4dd0e1', '', 'FALSE', 'FALSE'],
    ['c16', 'dev',  'ui_form.html',               'UI Form',                    'UI',           'General-purpose form prototype — validation, multi-step layout.',          '20 KB',  '#4dd0e1', '', 'FALSE', 'FALSE'],
    ['c17', 'dev',  'x.html',                     'X — Scratch Sandbox',        'Sandbox',      'Experimental page for quick prototyping before integration.',              '7 KB',   '#4dd0e1', '', 'FALSE', 'FALSE'],
    ['c18', 'comm', 'newsletter1fm.html',         'Newsletter 1FM',             'Newsletter',   'Branded email newsletter template — responsive layout, CTA buttons.',     '15 KB',  '#f06292', '', 'FALSE', 'FALSE'],
  ];
  cs.getRange(2, 1, cardRows.length, cHeaders.length).setValues(cardRows);

  cs.setColumnWidth(1,  80);
  cs.setColumnWidth(2,  80);
  cs.setColumnWidth(3,  230);
  cs.setColumnWidth(4,  210);
  cs.setColumnWidth(5,  100);
  cs.setColumnWidth(6,  350);
  cs.setColumnWidth(7,  70);
  cs.setColumnWidth(8,  90);
  cs.setColumnWidth(9,  200);
  cs.setColumnWidth(10, 65);
  cs.setColumnWidth(11, 65);
  cs.setFrozenRows(1);

  const grpRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(groupRows.map(r => r[0]))
    .setAllowInvalid(false)
    .build();
  cs.getRange(2, 2, 300, 1).setDataValidation(grpRule);

  const boolRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['FALSE', 'TRUE'])
    .setAllowInvalid(false)
    .build();
  cs.getRange(2, 10, 300, 2).setDataValidation(boolRule);

  Logger.log('✅ setupSheets complete. Sheets: "' + GROUPS_SHEET + '" and "' + CARDS_SHEET + '" created.');
  Logger.log('Next: Deploy → New deployment → Web app → Execute as Me → Anyone → copy /exec URL.');
}

// ── Quick test ─────────────────────────────────────────────────
function testDoGet() {
  const result = doGet({ parameter: {} });
  Logger.log(result.getContent().substring(0, 500));
}
