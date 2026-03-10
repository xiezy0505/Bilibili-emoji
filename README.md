# Bilibili Emote Tools & GIF Super Resolution

这个项目包含两个主要的 Python 脚本：

1.  `bilibili.py`: 用于下载 Bilibili 表情包。
2.  `process_gif.py`: 用于使用 Real-ESRGAN 对 GIF 动画进行超分辨率放大。

## 安装依赖

```bash
pip install requests
# 注意: process_gif.py 依赖 ffmpeg 和 realesrgan-ncnn-vulkan
```

## 使用说明

### 下载表情包
设置 `SESSDATA` 环境变量后运行：
```bash
python bilibili.py
```

### GIF 超分
```bash
python process_gif.py
# 或直接拖拽 GIF 文件到 clear.bat 上
```

## 注意事项

请勿在公共仓库提交包含个人信息的 `SESSDATA`。
