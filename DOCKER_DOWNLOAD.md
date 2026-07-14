# Docker 镜像下载

## openlab-robot-web.tar (2.1GB)

由于 Gitee release 附件配额限制（1GB），2.1GB 的 Docker 镜像无法直接上传到 release。

### 下载方式

**方式 1: Seafile 网盘（推荐）**

外网地址：https://123.60.230.221:19201/d/ffbfe2351f9c4fca8cac/
提取码：Yc2-4VgzN%

下载 `openlab-robot.zip`（含 openlab-robot-web.tar）

**方式 2: Gitee release 分卷（部分）**

release v1.0.0 已上传部分分卷（part.00 - part.10），可用以下命令下载并合并：

```bash
# 下载已上传的分卷
for i in $(seq -w 0 10); do
  wget "https://gitee.com/HongKongJournalist/OpenLab-Robot/releases/download/v1.0.0/openlab-robot-web.tar.part.$i"
done

# 合并（需要全部 22 个分卷，缺的从 Seafile 下载）
cat openlab-robot-web.tar.part.* > openlab-robot-web.tar
```

### 加载 Docker 镜像

```bash
docker load -i openlab-robot-web.tar
docker run -d -p 8080:8080 openlab-robot-web
```

## Skills

两个 skill 已在仓库 `skills/` 目录下：

- `skills/agent-eval/` — Agent 评测与优化（F1-F8 失败归因 + HRPO + reference 自动注入）
- `skills/mobile-bank-agent-eval/` — 手机银行 Agent 自动评测（4 阶段流水线 + 10 维度）

安装：
```bash
cp -r skills/agent-eval .claude/skills/
cp -r skills/mobile-bank-agent-eval .claude/skills/
```
