export async function onRequestPost(context) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const record = await context.request.json();
    if (!record || !record.answers) {
      return new Response(JSON.stringify({ error: 'Invalid data' }), { status: 400, headers });
    }

    const GITHUB_TOKEN = context.env.GITHUB_TOKEN;
    const REPO = '1332654743-bit/tennis-trajectory-demo';
    const FILE_PATH = 'survey-data/results.json';

    // Read existing data
    let existing = [];
    let sha = null;
    const getResp = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`, {
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'tennis-survey' }
    });
    if (getResp.ok) {
      const file = await getResp.json();
      sha = file.sha;
      existing = JSON.parse(atob(file.content));
    }

    // Append new record
    existing.push(record);

    // Write back
    const content = btoa(unescape(encodeURIComponent(JSON.stringify(existing, null, 2))));
    const putBody = { message: `Survey submission ${record.id || Date.now()}`, content };
    if (sha) putBody.sha = sha;

    const putResp = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`, {
      method: 'PUT',
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'tennis-survey' },
      body: JSON.stringify(putBody)
    });

    if (!putResp.ok) {
      const err = await putResp.text();
      return new Response(JSON.stringify({ error: err }), { status: 500, headers });
    }

    return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500, headers });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
  });
}
