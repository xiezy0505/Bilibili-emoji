import os
import shutil
import subprocess
import sys
import glob

# --- 配置区域 ---
# 请将 ffmpeg.exe 和 realesrgan-ncnn-vulkan.exe (及其 models 文件夹) 放入 bin 目录中
REAL_ESRGAN_FILENAME = "realesrgan-ncnn-vulkan.exe"
FFMPEG_FILENAME = "ffmpeg.exe"

# 模型可选: realesrgan-x4plus-anime (推荐动漫), realesrgan-x4plus
MODEL_NAME = "realesrgan-x4plus-anime"
# 放大倍率 (2, 3, 4)
SCALE = 4
# --- --- ---

# 全局变量
FFMPEG_EXE = "ffmpeg"
REAL_ESRGAN_EXE = REAL_ESRGAN_FILENAME

def check_dependencies():
    """检查 ffmpeg 和 realesrgan 是否可用，优先检查 bin 目录"""
    global FFMPEG_EXE, REAL_ESRGAN_EXE
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(script_dir, "bin")
    
    # 1. Check FFmpeg
    bin_ffmpeg = os.path.join(bin_dir, FFMPEG_FILENAME)
    local_ffmpeg = os.path.join(script_dir, FFMPEG_FILENAME)
    
    if os.path.exists(bin_ffmpeg):
        FFMPEG_EXE = bin_ffmpeg
    elif os.path.exists(local_ffmpeg):
        FFMPEG_EXE = local_ffmpeg
    elif shutil.which("ffmpeg"):
        FFMPEG_EXE = "ffmpeg"
    else:
        print("错误: 未找到 ffmpeg。")
        print("请将 ffmpeg.exe 放入 'bin' 文件夹中。")
        return False

    # 2. Check Real-ESRGAN
    bin_realesrgan = os.path.join(bin_dir, REAL_ESRGAN_FILENAME)
    local_realesrgan = os.path.join(script_dir, REAL_ESRGAN_FILENAME)
    
    if os.path.exists(bin_realesrgan):
        REAL_ESRGAN_EXE = bin_realesrgan
    elif os.path.exists(local_realesrgan):
        REAL_ESRGAN_EXE = local_realesrgan
    elif shutil.which(REAL_ESRGAN_FILENAME):
        REAL_ESRGAN_EXE = REAL_ESRGAN_FILENAME
    else:
        print(f"错误: 未找到 {REAL_ESRGAN_FILENAME}。")
        print(f"请将 {REAL_ESRGAN_FILENAME} 及其 models 文件夹放入 'bin' 文件夹中。")
        return False

    print(f"使用 FFmpeg: {FFMPEG_EXE}")
    print(f"使用 Real-ESRGAN: {REAL_ESRGAN_EXE}")
    return True

def get_fps(input_file):
    """获取 GIF 帧率"""
    try:
        cmd = [
            FFMPEG_EXE, '-i', input_file
        ]
        # ffmpeg -i info sent to stderr
        result = subprocess.run(cmd, capture_output=True, text=True)
        # Parse framerate from stderr
        # e.g. Stream #0:0: Video: gif, bgra, 300x300, 15 fps, 15 tbr, 100 tbn
        import re
        match = re.search(r'(\d+(?:\.\d+)?)\s+fps', result.stderr)
        if match:
            return float(match.group(1))
        
        print("警告: 无法从 ffmpeg 输出中检测帧率，使用默认值 15.0")
        return 15.0
    except Exception as e:
        print(f"获取帧率失败，将使用默认值 15.0: {e}")
        return 15.0

def process_gif(input_path, output_dir=None):
    if not os.path.exists(input_path):
        print(f"文件不存在: {input_path}")
        return

    print(f"\n正在处理: {input_path}")
    
    file_dir = os.path.dirname(input_path)
    file_name = os.path.basename(input_path)
    name_no_ext = os.path.splitext(file_name)[0]
    
    # 确定输出目录
    if output_dir:
        final_output_dir = output_dir
        if not os.path.exists(final_output_dir):
            try:
                os.makedirs(final_output_dir)
            except OSError as e:
                print(f"无法创建输出目录 {final_output_dir}: {e}")
                return
    else:
        final_output_dir = file_dir

    output_gif = os.path.join(final_output_dir, f"{name_no_ext}_HD.gif")

    # 临时目录跟随输出目录
    temp_root = final_output_dir
    temp_input_dir = os.path.join(temp_root, f"temp_frames_input_{os.getpid()}")
    temp_output_dir = os.path.join(temp_root, f"temp_frames_output_{os.getpid()}")
    palette_path = os.path.join(temp_root, f"palette_{os.getpid()}.png")

    # 清理旧临时文件
    if os.path.exists(temp_input_dir): shutil.rmtree(temp_input_dir)
    if os.path.exists(temp_output_dir): shutil.rmtree(temp_output_dir)
    os.makedirs(temp_input_dir)
    os.makedirs(temp_output_dir)

    try:
        # 1. 获取帧率
        fps = get_fps(input_path)
        print(f"检测到帧率: {fps:.2f}")

        # 2. 拆分帧
        print("[1/4] 拆分 GIF 帧...")
        subprocess.run([
            FFMPEG_EXE, "-i", input_path, 
            os.path.join(temp_input_dir, "frame_%04d.png")
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. 超分辨率处理
        print(f"[2/4] 使用 Real-ESRGAN 放大 (x{SCALE})...")
        
        cwd_path = os.path.dirname(REAL_ESRGAN_EXE)
        if not cwd_path: cwd_path = None

        cmd_upscale = [
            REAL_ESRGAN_EXE,
            "-i", temp_input_dir,
            "-o", temp_output_dir,
            "-n", MODEL_NAME,
            "-s", str(SCALE),
            "-f", "png"
        ]
        
        subprocess.run(cmd_upscale, check=True, cwd=cwd_path)

        # 4. 合成 GIF
        print("[3/4] 生成调色板...")
        subprocess.run([
            FFMPEG_EXE, "-i", os.path.join(temp_output_dir, "frame_%04d.png"),
            "-filter_complex", "palettegen=stats_mode=diff", "-y", palette_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("[4/4] 合成高清 GIF...")
        subprocess.run([
            FFMPEG_EXE, 
            "-framerate", str(fps),
            "-i", os.path.join(temp_output_dir, "frame_%04d.png"),
            "-i", palette_path,
            "-lavfi", "paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
            "-y", output_gif
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"成功! 输出文件: {output_gif}")

    except  subprocess.CalledProcessError as e:
        print(f"处理出错: {e}")
    finally:
        # 清理
        print("清理临时文件...")
        try:
            if os.path.exists(temp_input_dir): shutil.rmtree(temp_input_dir)
            if os.path.exists(temp_output_dir): shutil.rmtree(temp_output_dir)
            if os.path.exists(palette_path): os.remove(palette_path)
        except:
            pass

if __name__ == "__main__":
    if not check_dependencies():
        os.system("pause")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="GIF 超分辨率放大工具")
    parser.add_argument("-i", "--input", help="输入文件或文件夹路径")
    parser.add_argument("-o", "--output", help="输出文件夹路径 (可选)")
    parser.add_argument("files", nargs="*", help="拖拽传入的文件列表")

    args = parser.parse_args()

    target_files = []
    output_dir = None

    # 1. 确定输出目录
    if args.output:
        output_dir = args.output

    # 2. 确定输入文件列表
    if args.input:
        # 如果通过命令行指定了 input
        input_path = args.input.strip('"')
        if os.path.isdir(input_path):
            print(f"扫描文件夹: {input_path}")
            target_files.extend(glob.glob(os.path.join(input_path, "*.gif")))
            print(f"找到 {len(target_files)} 个 GIF 文件。")
        elif os.path.isfile(input_path):
            target_files.append(input_path)
        else:
            print(f"错误: 输入路径不存在: {input_path}")
            
    elif args.files:
        # 拖拽文件的情况
        target_files = args.files
        
    else:
        # 交互模式 (双击运行且没拖拽)
        print("\n--- 交互模式 ---")
        u_input = input("请输入输入路径 (直接回车扫描当前目录, 可输入文件夹或文件): ").strip()
        if u_input:
            u_input = u_input.strip('"')
            if os.path.isdir(u_input):
                print(f"扫描文件夹: {u_input}")
                target_files.extend(glob.glob(os.path.join(u_input, "*.gif")))
            elif os.path.isfile(u_input):
                target_files.append(u_input)
            else:
                print(f"错误: 路径不存在: {u_input}")
        
        # 尝试默认逻辑 (如果用户直接回车)
        if not u_input:
             print("扫描当前目录下所有 GIF 文件...")
             target_files.extend(glob.glob("*.gif"))

        u_output = input("请输入输出文件夹 (直接回车默认保存在原目录): ").strip()
        if u_output:
            output_dir = u_output.strip('"')

    if not target_files:
        print("未找到需要处理的 GIF 文件。")
        # 尝试查找 input.gif 作为最后的 fallback (兼容旧习惯)
        if os.path.exists("input.gif"):
            print("尝试处理默认文件 input.gif...")
            target_files.append("input.gif")

    if target_files:
        print(f"\n准备处理 {len(target_files)} 个任务...")
        for f in target_files:
            try:
                process_gif(f, output_dir)
            except Exception as e:
                print(f"处理文件 {f} 时出错: {e}")

    print("\n所有任务完成。")
    os.system("pause")
