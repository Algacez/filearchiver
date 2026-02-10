from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import subprocess
from datetime import datetime
from pathlib import Path
import json
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

BASE_DIR = Path('/root/filearchiver')
ALIAS_FILE = BASE_DIR / '.aliases.json'
META_FILE = BASE_DIR / '.metadata.json'
PAGE_SIZE = 10


def get_current_year_month():
    """获取当前年月目录"""
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


def load_aliases():
    """加载下载链接别名映射：alias_path -> target_path"""
    if not ALIAS_FILE.exists():
        return {}
    try:
        with ALIAS_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_aliases(aliases):
    """保存下载链接别名映射"""
    ensure_dir_exists(ALIAS_FILE.parent)
    with ALIAS_FILE.open('w', encoding='utf-8') as f:
        json.dump(aliases, f, ensure_ascii=True, indent=2)


def load_metadata():
    """加载文件元数据：target_path -> {source_url, original_name}"""
    if not META_FILE.exists():
        return {}
    try:
        with META_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_metadata(metadata):
    """保存文件元数据"""
    ensure_dir_exists(META_FILE.parent)
    with META_FILE.open('w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=True, indent=2)


def ensure_safe_rel_path(path_str):
    """确保相对路径安全且在 BASE_DIR 下"""
    cleaned = path_str.strip().lstrip('/').replace('\\', '/')
    if not cleaned or '..' in cleaned.split('/'):
        return None
    target = (BASE_DIR / cleaned).resolve()
    if not str(target).startswith(str(BASE_DIR.resolve())):
        return None
    return cleaned


def safe_target_dir(custom_path):
    """获取安全的目标目录（相对 BASE_DIR）"""
    if custom_path:
        rel = ensure_safe_rel_path(custom_path)
        if not rel:
            return None, None
        target_dir = (BASE_DIR / rel).resolve()
        return target_dir, rel
    year_month = get_current_year_month()
    target_dir = (BASE_DIR / year_month).resolve()
    return target_dir, year_month


def guess_filename_from_url(url):
    """从URL猜测文件名"""
    try:
        path = urlparse(url).path
        name = Path(path).name
        return name or 'downloaded_file'
    except Exception:
        return 'downloaded_file'


def apply_extension(original_name, new_name):
    """如果新文件名没有扩展名，则沿用原文件扩展名"""
    if not new_name:
        return new_name
    new_path = Path(new_name)
    if new_path.suffix:
        return new_name
    original_suffix = Path(original_name).suffix
    if original_suffix:
        return f"{new_name}{original_suffix}"
    return new_name


def build_alias_index(aliases):
    """构建 target_path -> [alias_paths] 反向索引"""
    index = {}
    for alias_path, target_path in aliases.items():
        index.setdefault(target_path, []).append(alias_path)
    return index


@app.route('/')
def index():
    """首页 - 下载页面"""
    return render_template('download.html', now=datetime.now())


@app.route('/download', methods=['POST'])
def download_file():
    """使用wget下载文件"""
    url = request.form.get('url', '').strip()
    custom_path = request.form.get('custom_path', '').strip()
    rename_to = request.form.get('rename_to', '').strip()

    if not url:
        flash('请输入文件地址', 'error')
        return redirect(url_for('index'))

    target_dir, target_rel = safe_target_dir(custom_path)
    if not target_dir:
        flash('自定义路径不合法', 'error')
        return redirect(url_for('index'))

    ensure_dir_exists(target_dir)

    try:
        original_name = guess_filename_from_url(url)
        final_name = rename_to.strip() if rename_to else original_name
        final_name = apply_extension(original_name, final_name)
        final_name = secure_filename(final_name)
        if not final_name:
            flash('文件名不合法', 'error')
            return redirect(url_for('index'))

        target_file = target_dir / final_name
        if target_file.exists():
            flash('目标文件已存在，请更换文件名', 'error')
            return redirect(url_for('index'))

        # 使用wget下载文件
        result = subprocess.run(
            ['wget', '-O', str(target_file), url],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )

        if result.returncode == 0:
            aliases = load_aliases()
            if original_name != final_name:
                alias_rel = ensure_safe_rel_path(f"{target_rel}/{original_name}")
                target_rel_path = ensure_safe_rel_path(f"{target_rel}/{final_name}")
                if alias_rel and target_rel_path:
                    aliases[alias_rel] = target_rel_path
                    save_aliases(aliases)
            metadata = load_metadata()
            target_rel_path = ensure_safe_rel_path(f"{target_rel}/{final_name}")
            if target_rel_path:
                metadata[target_rel_path] = {
                    'source_url': url,
                    'original_name': original_name
                }
                save_metadata(metadata)
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
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

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

    total_files = len(file_list)
    total_pages = max((total_files - 1) // PAGE_SIZE + 1, 1)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    files_page = file_list[start:end]

    aliases = load_aliases()
    alias_index = build_alias_index(aliases)
    metadata = load_metadata()
    for f in files_page:
        rel_path = f"{year}/{month}/{f['name']}"
        f['aliases'] = alias_index.get(rel_path, [])
        f['source_url'] = metadata.get(rel_path, {}).get('source_url')

    return render_template('files.html',
                          files=files_page,
                          total_files=total_files,
                          current_page=page,
                          total_pages=total_pages,
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
            aliases = load_aliases()
            target_rel = aliases.get(filepath)
            if target_rel:
                target_path = (BASE_DIR / target_rel).resolve()
                if target_path.exists() and target_path.is_file():
                    return send_file(target_path, as_attachment=True)
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

        aliases = load_aliases()
        target_rel = aliases.get(filepath)
        target_path = None
        if file_path.exists() and file_path.is_file():
            target_path = file_path
        elif target_rel:
            target_path = (BASE_DIR / target_rel).resolve()

        if target_path and target_path.exists() and target_path.is_file():
            target_rel_path = str(target_path.resolve()).replace(str(BASE_DIR.resolve()) + '/', '')
            target_path.unlink()
            aliases = {k: v for k, v in aliases.items() if v != target_rel_path}
            aliases.pop(filepath, None)
            save_aliases(aliases)
            metadata = load_metadata()
            if target_rel_path in metadata:
                metadata.pop(target_rel_path, None)
                save_metadata(metadata)
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


@app.route('/rename_file/<path:filepath>', methods=['POST'])
def rename_file(filepath):
    """重命名文件"""
    new_name = request.form.get('new_name', '').strip()
    if not new_name:
        flash('请输入新文件名', 'error')
        return redirect(url_for('files'))

    new_name = apply_extension(Path(filepath).name, new_name)
    new_name = secure_filename(new_name)
    if not new_name:
        flash('新文件名不合法', 'error')
        return redirect(url_for('files'))

    old_path = (BASE_DIR / filepath).resolve()
    try:
        if not str(old_path).startswith(str(BASE_DIR.resolve())):
            flash('非法的文件路径', 'error')
            return redirect(url_for('files'))

        if not old_path.exists() or not old_path.is_file():
            flash('文件不存在', 'error')
            return redirect(url_for('files'))

        new_path = old_path.parent / new_name
        if new_path.exists():
            flash('目标文件名已存在', 'error')
            return redirect(url_for('files'))

        old_rel = filepath
        new_rel = str(new_path.resolve()).replace(str(BASE_DIR.resolve()) + '/', '')
        old_path.rename(new_path)

        aliases = load_aliases()
        aliases[old_rel] = new_rel
        save_aliases(aliases)

        metadata = load_metadata()
        if old_rel in metadata:
            metadata[new_rel] = metadata.pop(old_rel)
            save_metadata(metadata)

        flash('文件重命名成功', 'success')
    except Exception as e:
        flash(f'重命名失败: {str(e)}', 'error')

    parts = filepath.split('/')
    if len(parts) >= 2:
        return redirect(url_for('files', year=parts[0], month=parts[1]))
    return redirect(url_for('files'))


@app.route('/upload', methods=['POST'])
def upload_file():
    """本地上传文件"""
    upload = request.files.get('file')
    custom_path = request.form.get('custom_path', '').strip()
    rename_to = request.form.get('rename_to', '').strip()

    if not upload or upload.filename == '':
        flash('请选择要上传的文件', 'error')
        return redirect(url_for('index'))

    target_dir, target_rel = safe_target_dir(custom_path)
    if not target_dir:
        flash('自定义路径不合法', 'error')
        return redirect(url_for('index'))

    ensure_dir_exists(target_dir)

    original_name = upload.filename
    final_name = rename_to.strip() if rename_to else original_name
    final_name = apply_extension(original_name, final_name)
    final_name = secure_filename(final_name)
    if not final_name:
        flash('文件名不合法', 'error')
        return redirect(url_for('index'))

    target_file = target_dir / final_name
    if target_file.exists():
        flash('目标文件已存在，请更换文件名', 'error')
        return redirect(url_for('index'))

    try:
        upload.save(target_file)

        aliases = load_aliases()
        if original_name != final_name:
            alias_rel = ensure_safe_rel_path(f"{target_rel}/{original_name}")
            target_rel_path = ensure_safe_rel_path(f"{target_rel}/{final_name}")
            if alias_rel and target_rel_path:
                aliases[alias_rel] = target_rel_path
                save_aliases(aliases)

        metadata = load_metadata()
        target_rel_path = ensure_safe_rel_path(f"{target_rel}/{final_name}")
        if target_rel_path:
            metadata[target_rel_path] = {
                'source_url': None,
                'original_name': original_name
            }
            save_metadata(metadata)

        flash('文件上传成功', 'success')
    except Exception as e:
        flash(f'上传失败: {str(e)}', 'error')

    return redirect(url_for('index'))


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
