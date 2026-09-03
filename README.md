# 日麻点数计算训练器

一个零第三方依赖的四人日麻点数训练器。程序使用 Python 标准库和 Tkinter，覆盖 1～13 番、亲家/子家、荣和/自摸，并提供正计时、正确率和平均完成时间统计。

## 功能

- 1～4 番常用符数点数表，以及满贯至累计役满。
- 亲家、子家、荣和、自摸随机出题。
- 普通题优先抽取常见的 30 符和 40 符；70 符仅占少量权重，1 番 70 符会进一步降频。
- 高番题按 7% 满贯、7% 跳满、3% 倍满、2% 三倍满、1% 累计役满抽取。
- 启动时先展示历史累计和最近 5 场，点击开始后才生成题目并正计时。
- 每题完成后立即保存正确率和平均用时，最多保留最近 1000 场摘要。
- 可在启动页自行选择统计 JSON 的保存位置，并安全复制或读取已有数据。
- 牌型、役种、宝牌和符数明细相互对应。
- 使用统一规格的高清 PNG 牌图；暗手连续排列，所有鸣牌集中在最右侧。

## 环境

- Python 3.8 或更高版本。
- Tkinter。Windows 和 macOS 的官方 Python 通常已包含；部分 Linux 发行版需要安装系统包 `python3-tk`。
- 不需要安装任何 Python 第三方包。

## 运行

Windows：

```powershell
py .\mahjong_score_trainer.py
```

macOS/Linux：

```bash
python3 ./mahjong_score_trainer.py
```

## 验证

```powershell
py .\mahjong_score_trainer.py --self-test
py -m py_compile .\mahjong_score_trainer.py
```

## 本地统计

统计文件只包含累计题数、正确数、总用时和场次摘要，不保存具体牌型、答案或输入内容。首次运行使用系统标准应用数据目录；启动页会显示完整路径，并可通过“更改保存位置”选择其他 `.json` 文件。

每道题从牌面显示完成后开始正计时，到首次提交时停止。正确答案、错误答案和格式错误都属于已完成题并计入平均用时；查看解析及等待下一题的时间不会计入。

更换位置时可以复制当前统计，或读取所选文件。复制到已有文件前会自动生成时间戳备份，旧位置的文件不会被删除。统计和路径配置都采用临时文件加原子替换，损坏文件会隔离备份并给出提示。

## 贡献

所有修改遵循 [贡献指南](CONTRIBUTING.md)。开始开发前还应阅读 [项目约束](AGENTS.md) 和 [开发规则](CODEX_RULES.md)。

## 素材

当前牌图来自 [FluffyStuff/riichi-mahjong-tiles](https://github.com/FluffyStuff/riichi-mahjong-tiles)，按 CC0 1.0 / Public Domain 发布。完整来源与许可证记录见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [素材许可证](assets/tiles/LICENSE.md)。项目代码与第三方素材分别遵循各自的权利声明。

可以替换为自己的牌图，但应保留现有文件名、透明背景和 600×800 像素规格。程序启动时会检查全部 39 个必需文件及其尺寸；替换不完整时会显示明确错误，不会混用两套图案。

