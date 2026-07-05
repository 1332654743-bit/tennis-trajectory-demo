export async function onRequestGet(context) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const GITHUB_TOKEN = context.env.GITHUB_TOKEN;
    const REPO = '1332654743-bit/tennis-trajectory-demo';
    const FILE_PATH = 'survey-data/results.json';

    const getResp = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`, {
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'tennis-survey' }
    });

    if (!getResp.ok) {
      return new Response(JSON.stringify([]), { status: 200, headers });
    }

    const file = await getResp.json();
    const data = JSON.parse(atob(file.content));
    return new Response(JSON.stringify(data), { status: 200, headers });
  } catch (e) {
    return new Response(JSON.stringify([]), { status: 200, headers });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
  });
}
