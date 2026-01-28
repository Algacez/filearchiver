# FileArchiver - 文件下载与管理系统

一个基于Flask的WebUI应用，用于下载文件并按月份管理。

## 功能特性

- **文件下载**: 输入URL，使用wget自动下载文件到服务器
- **自动归档**: 文件按年/月自动分类存储（如 /root/filearchiver/2026/01/）
- **文件浏览**: 按月份查看文件列表
- **月份切换**: 通过按钮或下拉菜单快速切换月份
- **文件操作**: 支持下载和删除服务器上的文件

## 安装

1. 安装Python依赖：
```bash
pip install -r requirements.txt
```

2. 确保系统已安装wget：
```bash
# Ubuntu/Debian
sudo apt-get install wget

# CentOS/RHEL
sudo yum install wget

# macOS
brew install wget
```

3. 创建存储目录并设置权限：
```bash
sudo mkdir -p /root/filearchiver
sudo chmod 755 /root/filearchiver
```

## 运行

```bash
python app.py
```

应用将在 `http://0.0.0.0:5000` 上启动。

## 使用说明

### 下载文件
1. 访问首页
2. 输入文件URL地址
3. 点击"开始下载"按钮
4. 文件将自动下载到当前月份的目录

### 浏览文件
1. 点击顶部导航的"浏览文件"
2. 使用"上个月/下个月"按钮切换月份
3. 或使用下拉菜单快速跳转到指定月份
4. 点击"下载"按钮可下载文件到本地
5. 点击"删除"按钮可删除服务器上的文件

## 目录结构

```
filearchiver/
├── app.py                 # Flask主应用
├── requirements.txt       # Python依赖
├── templates/
│   ├── download.html     # 下载页面模板
│   └── files.html        # 文件浏览页面模板
└── README.md             # 本文件
```

## 注意事项

- 默认下载超时时间为5分钟
- 确保有足够的磁盘空间
- 文件路径安全检查防止目录遍历攻击
- 建议在生产环境使用HTTPS和适当的身份验证

## 开发模式

当前应用以debug模式运行，适合开发测试。生产环境请修改 `app.py` 的最后一行：

```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

## 自定义配置

可在 `app.py` 中修改以下配置：
- `BASE_DIR`: 修改存储根目录
- `timeout`: 修改下载超时时间
- `host` 和 `port`: 修改监听地址和端口
