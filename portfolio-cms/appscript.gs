/**
 * Google Apps Script — Project Hub Sync
 *
 * Setup:
 * 1. Open your Google Sheet (columns: id, group, url, title, tag, desc, size, color, faded, newTab, thumbUrl)
 * 2. Create a second sheet named "groups" (columns: id, label, icon, color)
 * 3. In the sheet: Extensions → Apps Script → paste this code → Save
 * 4. Deploy → New deployment → Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 5. Copy the Web App URL → paste it in Project Hub Admin → Google Sheet Sync
 */

function doGet(e) {
  const callback = e.parameter.callback || 'callback';

  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // ── Read cards ──
    const cardSheet = ss.getSheetByName('cards') || ss.getSheets()[0];
    const cardData  = cardSheet.getDataRange().getValues();
    const cardHeaders = cardData[0].map(h => String(h).toLowerCase().trim());
    const cards = cardData.slice(1).filter(r => r[0]).map(row => {
      const obj = {};
      cardHeaders.forEach((h, i) => obj[h] = row[i] !== undefined ? row[i] : '');
      return {
        id:       String(obj.id      || ('c' + Date.now() + Math.random())),
        group:    String(obj.group   || 'dev'),
        url:      String(obj.url     || ''),
        title:    String(obj.title   || ''),
        tag:      String(obj.tag     || ''),
        desc:     String(obj.desc    || ''),
        size:     String(obj.size    || ''),
        color:    String(obj.color   || '#4f7cff'),
        thumbUrl: String(obj.thumburl|| ''),
        faded:    obj.faded   === true || String(obj.faded).toLowerCase()   === 'true',
        newTab:   obj.newtab  === true || String(obj.newtab).toLowerCase()  === 'true',
      };
    });

    // ── Read groups ──
    let groups = [];
    const grpSheet = ss.getSheetByName('groups');
    if (grpSheet) {
      const grpData    = grpSheet.getDataRange().getValues();
      const grpHeaders = grpData[0].map(h => String(h).toLowerCase().trim());
      groups = grpData.slice(1).filter(r => r[0]).map(row => {
        const obj = {};
        grpHeaders.forEach((h, i) => obj[h] = row[i] !== undefined ? row[i] : '');
        return {
          id:    String(obj.id    || ''),
          label: String(obj.label || ''),
          icon:  String(obj.icon  || 'folder'),
          color: String(obj.color || '#4f7cff'),
        };
      });
    }

    const payload = {
      groups,
      cards,
      _count:  cards.length,
      _synced: new Date().toISOString(),
    };

    return ContentService
      .createTextOutput(`${callback}(${JSON.stringify(payload)})`)
      .setMimeType(ContentService.MimeType.JAVASCRIPT);

  } catch (err) {
    const errPayload = { error: err.message };
    return ContentService
      .createTextOutput(`${callback}(${JSON.stringify(errPayload)})`)
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
}
