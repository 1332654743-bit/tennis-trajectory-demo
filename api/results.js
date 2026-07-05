export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
    const REPO = '1332654743-bit/tennis-trajectory-demo';
    const FILE_PATH = 'survey-data/results.json';

    const getResp = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`, {
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json' }
    });

    if (!getResp.ok) {
      return res.status(200).json([]);
    }

    const file = await getResp.json();
    const data = JSON.parse(Buffer.from(file.content, 'base64').toString('utf-8'));
    return res.status(200).json(data);
  } catch (e) {
    return res.status(200).json([]);
  }
}
