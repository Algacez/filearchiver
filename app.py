from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
import os
import subprocess
from datetime import datetime
from pathlib import Path
import calendar

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

BASE_DIR = Path('/root/filearchiver')


def get_current_year_month():
    """获取当前年月目��"""
    now = datetime.now()
    return now.strftime('%Y/%m')


def ensure_dir_exists(path):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)


def get_available_months():
    """获取所有可用的月份"""
    if not BASE_DIR.exists():
        return []

    months = []
    for year_dir in sorted(BASE_DIR.iterdir(), reverse=True):
        if year_dir.is_dir() and year_dir.name.isdigit():
            for month_dir in sorted(year_dir.iterdir(), reverse=True):
                if month_dir.is_dir() and month_dir.name.isdigit():
                    months.append({
                        'year': year_dir.name,
                        'month': month_dir.name,
                        'path': month_dir,
                        'label': f"{year_dir.name}年{month_dir.name}月"
                    })
    return months


def get_files_in_month(year, month):
    """获取指定月份的文件列表"""
    month_path = BASE_DIR / year / month
    if not month_path.exists():
        return []

    files = []
    for file_path in sorted(month_path.iterdir()):
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                'name': file_path.name,
                'path': file_path,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime)
            })
    return files


@app.route('/')
def index():
    """首页 - 下载页面"""
    return render_template('download.html', now=datetime.now())


@app.route('/download', methods=['POST'])
def download_file():
    """使用wget下载文件"""
    url = request.form.get('url', '').strip()

    if not url:
        flash('请输入文件地址', 'error')
        return redirect(url_for('index'))

    # 创建目标目录
    year_month = get_current_year_month()
    target_dir = BASE_DIR / year_month
    ensure_dir_exists(target_dir)

    try:
        # 使用wget下载文件
        result = subprocess.run(
            ['wget', '-P', str(target_dir), url],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )

        if result.returncode == 0:
            flash(f'文件下载成功到: {target_dir}', 'success')
        else:
            flash(f'下载失败: {result.stderr}', 'error')
    except subprocess.TimeoutExpired:
        flash('下载超时（5分钟）', 'error')
    except Exception as e:
        flash(f'下载出错: {str(e)}', 'error')

    return redirect(url_for('index'))


@app.route('/files')
def files():
    """文件浏览页面"""
    year = request.args.get('year', datetime.now().strftime('%Y'))
    month = request.args.get('month', datetime.now().strftime('%m'))

    # 获取当前月份的文件
    file_list = get_files_in_month(year, month)

    # 获取所有可用月份
    available_months = get_available_months()

    # 查找当前月份的索引
    current_index = -1
    for i, m in enumerate(available_months):
        if m['year'] == year and m['month'] == month:
            current_index = i
            break

    # 计算上个月和下个月
    prev_month = available_months[current_index + 1] if current_index < len(available_months) - 1 else None
    next_month = available_months[current_index - 1] if current_index > 0 else None

    return render_template('files.html',
                          files=file_list,
                          current_year=year,
                          current_month=month,
                          current_label=f"{year}年{month}月",
                          prev_month=prev_month,
                          next_month=next_month,
                          available_months=available_months)


@app.route('/download_file/<path:filepath>')
def download(filepath):
    """下载服务器上的文件"""
    # 安全检查：确保文件路径在BASE_DIR下
    file_path = BASE_DIR / filepath
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(BASE_DIR.resolve())):
            flash('非法的文件路径', 'error')
            return redirect(url_for('files'))

        if file_path.exists() and file_path.is_file():
            return send_file(file_path, as_attachment=True)
        else:
            flash('文件不存在', 'error')
            return redirect(url_for('files'))
    except Exception as e:
        flash(f'下载失败: {str(e)}', 'error')
        return redirect(url_for('files'))


@app.route('/delete_file/<path:filepath>', methods=['POST'])
def delete_file(filepath):
    """删除文件"""
    file_path = BASE_DIR / filepath
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(BASE_DIR.resolve())):
            flash('非法的文件路径', 'error')
            return redirect(url_for('files'))

        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            flash('文件删除成功', 'success')
        else:
            flash('文件不存在', 'error')
    except Exception as e:
        flash(f'删除失败: {str(e)}', 'error')

    # 重定向回文件所在月份的页面
    parts = filepath.split('/')
    if len(parts) >= 2:
        return redirect(url_for('files', year=parts[0], month=parts[1]))
    return redirect(url_for('files'))


def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


# 注册自定义过滤器
app.jinja_env.filters['format_size'] = format_size

if __name__ == '__main__':
    # 确保基础目录存在
    ensure_dir_exists(BASE_DIR)
    app.run(host='0.0.0.0', port=5001, debug=True)
