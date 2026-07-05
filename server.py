#!/usr/bin/env python3
"""
网球轨迹调研 - 本地服务器
同时提供静态文件托管 + 数据收集 API

启动: python3 server.py
访问: http://localhost:8080/tennis-survey.html (问卷)
      http://localhost:8080/survey-dashboard.html (看板)
"""

import json
import os
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

PORT = 8080
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'survey-data')

os.makedirs(DATA_DIR, exist_ok=True)


class SurveyHandler(SimpleHTTPRequestHandler):

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/api/submit':
            self._handle_submit()
        elif path == '/api/clear':
            self._handle_clear()
        elif path == '/api/restore':
            self._handle_restore()
        else:
            self.send_error(404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/results':
            self._handle_results()
        else:
            super().do_GET()

    def _handle_submit(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, 'Invalid JSON')
            return

        seq = len(os.listdir(DATA_DIR)) + 1
        ts = time.strftime('%Y%m%d_%H%M%S')
        filename = f'{seq:03d}_{ts}.json'
        filepath = os.path.join(DATA_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'file': filename}).encode())
        print(f'  📥 收到提交 #{seq} -> {filename}')

    def _handle_clear(self):
        # 移入回收站而非删除，支持恢复
        trash_dir = os.path.join(os.path.dirname(DATA_DIR), 'survey-data-trash')
        ts = time.strftime('%Y%m%d_%H%M%S')
        batch_dir = os.path.join(trash_dir, f'cleared_{ts}')
        os.makedirs(batch_dir, exist_ok=True)
        count = 0
        for fname in os.listdir(DATA_DIR):
            if fname.endswith('.json'):
                os.rename(os.path.join(DATA_DIR, fname), os.path.join(batch_dir, fname))
                count += 1
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'deleted': count, 'batch': f'cleared_{ts}'}).encode())
        print(f'  🗑 已清空 {count} 条数据 → 回收站 {batch_dir}')

    def _handle_restore(self):
        # 恢复最近一次清空的数据
        trash_dir = os.path.join(os.path.dirname(DATA_DIR), 'survey-data-trash')
        if not os.path.exists(trash_dir):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': False, 'msg': '回收站为空'}).encode())
            return
        batches = sorted([d for d in os.listdir(trash_dir) if d.startswith('cleared_')])
        if not batches:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': False, 'msg': '回收站为空'}).encode())
            return
        latest = batches[-1]
        batch_dir = os.path.join(trash_dir, latest)
        count = 0
        for fname in os.listdir(batch_dir):
            if fname.endswith('.json'):
                os.rename(os.path.join(batch_dir, fname), os.path.join(DATA_DIR, fname))
                count += 1
        os.rmdir(batch_dir)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'restored': count, 'batch': latest}).encode())
        print(f'  ♻️ 已恢复 {count} 条数据 ← {latest}')

    def _handle_results(self):
        submissions = []
        for fname in sorted(os.listdir(DATA_DIR)):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(DATA_DIR, fname)
            with open(fpath, 'r', encoding='utf-8') as f:
                submissions.append(json.load(f))

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(submissions, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(('0.0.0.0', PORT), SurveyHandler)
    print(f'🎾 网球轨迹调研服务器已启动')
    print(f'   问卷页面: http://localhost:{PORT}/tennis-survey.html')
    print(f'   分析看板: http://localhost:{PORT}/survey-dashboard.html')
    print(f'   数据目录: {DATA_DIR}')
    print(f'   按 Ctrl+C 停止\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
