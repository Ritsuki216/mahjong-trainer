# 日麻点数计算训练器

一个零第三方依赖的四人日麻点数训练器。程序使用 Python 标准库和 Tkinter，覆盖 1～13 番、亲家/子家、荣和/自摸，并提供 5 秒计时和正确率统计。

## 功能

- 1～4 番常用符数点数表，以及满贯至累计役满。
- 亲家、子家、荣和、自摸随机出题。
- 高番题按 7% 满贯、7% 跳满、3% 倍满、2% 三倍满、1% 累计役满抽取。
- 允许超时后继续作答，并分别统计答案正确率与 5 秒内答对率。
- 牌型、役种、宝牌和符数明细相互对应。

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

## 贡献

所有修改遵循 [贡献指南](CONTRIBUTING.md)。开始开发前还应阅读 [项目约束](AGENTS.md) 和 [开发规则](CODEX_RULES.md)。

## 素材

牌图素材及其许可证会记录在 `THIRD_PARTY_NOTICES.md`。项目代码与第三方素材分别遵循各自的权利声明。

