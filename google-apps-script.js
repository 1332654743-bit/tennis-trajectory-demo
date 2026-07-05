/**
 * Google Apps Script - 问卷数据收集后端
 *
 * 使用方法：
 * 1. 打开 Google Sheets，创建一个新的电子表格
 * 2. 菜单 → 扩展程序 → Apps Script
 * 3. 把下面的代码粘贴进去，替换掉默认内容
 * 4. 点击"部署" → "新建部署"
 * 5. 类型选"Web 应用"
 * 6. "执行者"选"我自己"
 * 7. "谁有权访问"选"任何人"
 * 8. 点击"部署"，授权，拿到 Web App URL
 * 9. 把 URL 填到 tennis-survey-part2.html 中的 GOOGLE_SCRIPT_URL 变量里
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);

    // 第一次使用时写入表头
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        '提交时间', '提交ID', '类型',
        '球场背景', '动作轨迹', '球飞出', '击中提示', '播放速度', '人物模型', '模型改善',
        '运镜选择', '数据展示', '图表展示', '分享意愿', '分享渠道',
        '意见汇总', '原始JSON'
      ]);
    }

    var answers = data.answers || {};
    var allComments = Object.values(answers).map(function(v) { return v && v.comment ? v.comment : ''; }).filter(Boolean).join(' | ');

    var row = [
      data.timestamp || new Date().toISOString(),
      data.id || '',
      data.part || '',
      getChoice(answers.court),
      getChoice(answers.style),
      getChoice(answers.ballfly),
      getChoice(answers.marker),
      getChoice(answers.speed),
      getChoice(answers.model),
      getFollowup(answers.model),
      getChoice(answers.camera),
      getMultiChoice(answers.data),
      getChoice(answers.chart),
      getChoice(answers.share),
      getFollowup(answers.share),
      allComments,
      JSON.stringify(data)
    ];

    sheet.appendRow(row);

    return ContentService.createTextOutput(JSON.stringify({ok: true}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ok: false, error: err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var rows = sheet.getDataRange().getValues();
    if (rows.length <= 1) {
      return ContentService.createTextOutput(JSON.stringify([]))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 返回原始 JSON 数据（最后一列）
    var results = [];
    for (var i = 1; i < rows.length; i++) {
      try {
        var raw = JSON.parse(rows[i][rows[i].length - 1]);
        results.push(raw);
      } catch(e) {}
    }

    return ContentService.createTextOutput(JSON.stringify(results))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify([]))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function getChoice(ans) {
  if (!ans) return '';
  return ans.choice || '';
}

function getMultiChoice(ans) {
  if (!ans) return '';
  var choices = ans.choice || ans.choices || [];
  if (Array.isArray(choices)) return choices.join('+');
  return choices;
}

function getFollowup(ans) {
  if (!ans || !ans.followup) return '';
  return ans.followup.join('+');
}
