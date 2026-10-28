// The Artifact needs its downloads capability; a normal website can use the
// browser's built-in file download.
export async function saveWorkbook(data, filename, downloads, browser = globalThis) {
  if (downloads) return downloads.save({ filename, data });

  const blob = new browser.Blob([data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const url = browser.URL.createObjectURL(blob);
  const anchor = browser.document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  browser.document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    browser.setTimeout(() => browser.URL.revokeObjectURL(url), 1000);
  }
  return { status: 'saved' };
}
