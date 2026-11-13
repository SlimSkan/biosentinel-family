// BioSentinel Family - gets the text out of a PDF lab report, INSIDE the browser.
// The file never leaves the phone: pdf.js (Mozilla's PDF reader, used by Firefox) reads it here.
const PDFJS = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build";

let pdfjs = null;
async function loadPdfJs() {
  if (!pdfjs) {
    pdfjs = await import(`${PDFJS}/pdf.min.mjs`);
    pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS}/pdf.worker.min.mjs`;
  }
  return pdfjs;
}

/** Returns the PDF's text with one line per visual row (a table row stays on one line). */
export async function pdfToText(file) {
  const lib = await loadPdfJs();
  const doc = await lib.getDocument({ data: await file.arrayBuffer() }).promise;
  const lines = [];
  for (let p = 1; p <= Math.min(doc.numPages, 10); p++) {           // reports are short; cap at 10 pages
    const content = await (await doc.getPage(p)).getTextContent();
    // Group text pieces by their vertical position (y), then sort each row left to right (x).
    const rows = new Map();
    for (const item of content.items) {
      if (!item.str.trim()) continue;
      const y = Math.round(item.transform[5] / 3);                   // pieces within ~3 points share a row
      if (!rows.has(y)) rows.set(y, []);
      rows.get(y).push({ x: item.transform[4], s: item.str });
    }
    [...rows.entries()].sort((a, b) => b[0] - a[0])                  // top of the page first
      .forEach(([, items]) => lines.push(items.sort((a, b) => a.x - b.x).map((i) => i.s).join("  ")));
  }
  return lines.join("\n");
}
