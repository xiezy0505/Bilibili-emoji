import os
import shutil
import subprocess
import sys
import glob

# --- 配置区域 ---
# 请确保 realesrgan-ncnn-vulkan.exe 在此脚本同级目录或系统 PATH 环境变量中
REAL_ESRGAN_EXE = "realesrgan-ncnn-vulkan.exe"
# 模型可选: realesrgan-x4plus-anime (推荐动漫), realesrgan-x4plus
MODEL_NAME = "realesrgan-x4plus-anime"
# 放大倍率 (2, 3, 4)
SCALE = 4
# --- --- ---

def check_dependencies():
    """检查 ffmpeg 和 realesrgan 是否可用"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check 1: FFmpeg
    ffmpeg_exe = "ffmpeg"
    # 尝试在当前目录找 ffmpeg.exe
    local_ffmpeg = os.path.join(script_dir, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        ffmpeg_exe = local_ffmpeg
    
    try:
        subprocess.run([ffmpeg_exe, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("错误: 未找到 ffmpeg。")
        print("请尝试以下解决方案之一：")
        print("1. 确保已安装 ffmpeg 并将其 bin 目录添加到系统环境变量 PATH 中。")
        print("   (注意: 添加环境变量后，必须完全重启 VS Code 或终端才能生效)")
        print(f"2. 或者，将 ffmpeg.exe 复制到此脚本同级目录: {script_dir}")
        return False

    # Check 2: Real-ESRGAN
    # 尝试直接运行命令，或者检查当前目录是否存在
    # 优先级: 脚本同级目录 > PATH
    local_realesrgan = os.path.join(script_dir, REAL_ESRGAN_EXE)
    
    realesrgan_path = None
    if os.path.exists(local_realesrgan):
        realesrgan_path = local_realesrgan
    elif shutil.which(REAL_ESRGAN_EXE):
        realesrgan_path = REAL_ESRGAN_EXE
        
    if not realesrgan_path:
        print(f"错误: 未找到 {REAL_ESRGAN_EXE}。")
        print("请尝试以下解决方案之一：")
        print(f"1. 将 {REAL_ESRGAN_EXE} 复制到此脚本同级目录: {script_dir}")
        print("2. 或者，将其所在的目录添加到系统环境变量 PATH 中。")
        print("   (注意: 添加环境变量后，必须完全重启 VS Code 或终端才能生效)")
        return False

    # 更新全局变量，确保后续使用的是找到的路径
    global REAL_ESRGAN_EXE_PATH
    REAL_ESRGAN_EXE_PATH = realesrgan_path
    
    return True

def get_fps(input_file):
    """获取 GIF 帧率"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fps_str = result.stdout.strip()
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            return num / den
        return float(fps_str)
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

    # 临时目录跟随输出目录，避免跨盘问题
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
            "ffmpeg", "-i", input_path, 
            os.path.join(temp_input_dir, "frame_%04d.png")
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. 超分辨率处理
        print(f"[2/4] 使用 Real-ESRGAN 放大 (x{SCALE})...")
        # 构建 Real-ESRGAN 命令
        exe_path = REAL_ESRGAN_EXE
        if not shutil.which(REAL_ESRGAN_EXE) and os.path.exists(REAL_ESRGAN_EXE):
             exe_path = os.path.abspath(REAL_ESRGAN_EXE)
             
        cmd_upscale = [
            exe_path,
            "-i", temp_input_dir,
            "-o", temp_output_dir,
            "-n", MODEL_NAME,
            "-s", str(SCALE),
            "-f", "png"
        ]
        subprocess.run(cmd_upscale, check=True)

        # 4. 合成 GIF
        print("[3/4] 生成调色板...")
        # 生成调色板以获得更好画质
        subprocess.run([
            "ffmpeg", "-i", os.path.join(temp_output_dir, "frame_%04d.png"),
            "-filter_complex", "palettegen=stats_mode=diff", "-y", palette_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("[4/4] 合成高清 GIF...")
        subprocess.run([
            "ffmpeg", 
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
        if os.path.exists(temp_input_dir): shutil.rmtree(temp_input_dir)
        if os.path.exists(temp_output_dir): shutil.rmtree(temp_output_dir)
        if os.path.exists(palette_path): os.remove(palette_path)

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
