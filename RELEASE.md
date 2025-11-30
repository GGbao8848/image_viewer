# 发布指南 / Release Guide

本文档说明如何发布新版本的 Self Tools。

## 发布流程

### 1. 准备发布

确保所有更改已完成并测试通过：

```bash
# 运行本地测试
python backend/main.py
# 确保所有功能正常工作
```

### 2. 更新版本信息

在发布前，建议更新以下内容：
- `README.md` - 更新版本号和更新日志
- 确认 `requirements.txt` 包含所有依赖

### 3. 创建版本标签

使用语义化版本号（Semantic Versioning）：

```bash
# 提交所有更改
git add .
git commit -m "Release v1.0.0: 添加自动打包功能"

# 创建标签（必须以 v 开头）
git tag v1.0.0

# 或创建带注释的标签（推荐）
git tag -a v1.0.0 -m "Release version 1.0.0"
```

**版本号规范：**
- `v1.0.0` - 主要版本（重大更新）
- `v1.1.0` - 次要版本（新功能）
- `v1.0.1` - 补丁版本（Bug 修复）

### 4. 推送到 GitHub

```bash
# 推送代码
git push origin master

# 推送标签（这会触发自动构建）
git push origin v1.0.0

# 或推送所有标签
git push origin --tags
```

### 5. 监控构建过程

1. 访问 GitHub 仓库的 **Actions** 标签页
2. 查看 "Build and Release" 工作流运行状态
3. 等待所有平台构建完成（约 5-10 分钟）

### 6. 验证发布

构建完成后：

1. 访问 **Releases** 页面
2. 确认新版本已创建
3. 检查三个平台的可执行文件是否都已上传：
   - `image_viewer-windows.exe`
   - `image_viewer-macos`
   - `image_viewer-linux`

## 本地测试打包

在推送标签前，可以本地测试打包：

```bash
# 安装 PyInstaller
pip install pyinstaller

# 运行打包
pyinstaller build.spec

# 测试生成的可执行文件
./dist/image_viewer  # macOS/Linux
dist\image_viewer.exe  # Windows
```

## 预发布版本

如果要创建测试版本：

```bash
# 创建预发布标签
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

在 GitHub Release 中，可以手动标记为 "Pre-release"。

## 删除标签

如果需要删除错误的标签：

```bash
# 删除本地标签
git tag -d v1.0.0

# 删除远程标签
git push origin :refs/tags/v1.0.0
```

## 故障排除

### 构建失败

1. 检查 Actions 日志查看错误信息
2. 确认 `requirements.txt` 中的依赖版本兼容
3. 验证 `build.spec` 配置正确

### 文件缺失

如果打包后缺少文件：
1. 检查 `build.spec` 中的 `datas` 配置
2. 确保所有资源文件都被包含

### 运行时错误

如果可执行文件无法运行：
1. 检查 `hiddenimports` 是否包含所有必要的模块
2. 在本地使用 PyInstaller 测试
3. 查看控制台输出的错误信息

## 回滚版本

如果发现问题需要回滚：

1. 在 GitHub Releases 页面删除有问题的版本
2. 创建新的修复版本
3. 推送新标签重新构建

## 最佳实践

- ✅ 每次发布前在本地充分测试
- ✅ 使用语义化版本号
- ✅ 在标签消息中说明主要更改
- ✅ 保持 README 和文档更新
- ✅ 测试所有平台的可执行文件
- ❌ 不要删除已发布的正式版本
- ❌ 不要在未测试的情况下推送标签
