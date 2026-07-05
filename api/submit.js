export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const record = req.body;
    if (!record || !record.answers) {
      return res.status(400).json({ error: 'Invalid data' });
    }

    const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
    const REPO = '1332654743-bit/tennis-trajectory-demo';
    const FILE_PATH = 'survey-data/results.json';

    // Read existing data
    let existing = [];
    let sha = null;
    const getResp = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`, {
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json' }
    });
    if (getResp.ok) {
      const file = await getResp.json();
      sha = file.sha;
      existing = JSON.parse(Buffer.from(file.content, 'base64').toString('utf-8'));
    }

    // Append new record
    existing.push(record);

    // Write back
    const content = Buffer.from(JSON.stringify(existing, null, 2)).toString('base64');
    const putBody = { message: `Survey submission ${record.id || Date.now()}`, content, sha };
    if (!sha) delete putBody.sha;

    const putResp = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`, {
      method: 'PUT',
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json' },
      body: JSON.stringify(putBody)
    });

    if (!putResp.ok) {
      const err = await putResp.text();
      return res.status(500).json({ error: err });
    }

    return res.status(200).json({ ok: true });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
