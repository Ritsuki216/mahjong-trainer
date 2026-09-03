# 贡献指南

本指南适用于代码、文档、素材和配置修改。目标是让 `main` 始终保持可运行，并让每项改动都可验证、可审查、可回退。

## 不变原则

- `main` 是唯一长期分支，必须保持已验证、可启动。
- 每项工作使用一个短生命周期分支，一个分支只处理一个主题。
- 不直接在 `main` 上开发、提交或强制推送。
- 本地验证通过后先提供摘要、验证结果、风险和文件列表；确认后再提交、推送或合并。
- 不提交令牌、密钥、日志、缓存、虚拟环境或来源不明的素材。

## 标准流程

### 1. 更新基线

```powershell
git status --short --branch
git fetch origin --prune
git switch main
git pull --ff-only origin main
```

工作区不干净时先辨认并保护已有修改，不得擅自覆盖或清理。

### 2. 建立任务分支

分支名使用以下前缀：

- `feat/名称`：新功能。
- `fix/名称`：缺陷修复。
- `docs/名称`：文档。
- `chore/名称`：工程维护。
- `refactor/名称`：不改变行为的重构。

推荐使用独立 worktree：

```powershell
git worktree add -b feat/example E:\mahjong-trainer-worktrees\feat-example main
```

### 3. 验证

```powershell
py .\mahjong_score_trainer.py --self-test
py -m py_compile .\mahjong_score_trainer.py
```

界面修改还要执行 Tkinter 创建与绘制 smoke test，并人工检查图片清晰度、键盘流程和常见显示缩放。

### 4. 提交与 PR

确认变更后，只暂存当前主题文件：

```powershell
git add <本任务文件>
git commit -m "feat: describe the change"
git push -u origin feat/example
```

创建 PR，等待 CI 通过后再合并。禁止绕过失败检查或把无关改动塞进同一提交。

### 5. 合并后清理

```powershell
git switch main
git pull --ff-only origin main
git worktree remove E:\mahjong-trainer-worktrees\feat-example
git branch -d feat/example
git push origin --delete feat/example
git status --short --branch
```

删除分支或 worktree 前必须确认 PR 已合并且没有未保存修改。

## 提交前检查清单

- [ ] 分支来自最新 `origin/main`，且只包含一个主题。
- [ ] `--self-test` 和 `py_compile` 通过。
- [ ] 涉及 UI 时完成 Tkinter smoke test和人工检查。
- [ ] 牌图、符数、番数、役种和点数保持一致。
- [ ] 第三方素材来源与许可证已记录。
- [ ] 未提交缓存、日志、令牌、密钥或个人数据。
- [ ] 已说明已知限制和回退方式。

