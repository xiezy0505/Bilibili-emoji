import os
import shutil
import subprocess
import sys
import glob
import shlex

# --- 配置区域 ---
# 将 ffmpeg.exe 和 realesrgan-ncnn-vulkan.exe (及其 models 文件夹) 放入 bin 目录中
REAL_ESRGAN_FILENAME = "realesrgan-ncnn-vulkan.exe"

# 模型可选: realesrgan-x4plus-anime (推荐动漫), realesrgan-x4plus
MODEL_NAME = "realesrgan-x4plus-anime"
# 放大倍率 (2, 3, 4)
SCALE = 4
# --- --- ---

def get_base_path():
    """获取脚本或可执行文件的基础路径"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def check_dependencies():
    """检查 realesrgan 是否可用，优先检查 bin 目录"""
    script_dir = get_base_path()
    bin_dir = os.path.join(script_dir, "bin")
    
    # Check: Real-ESRGAN
    # 优先检查 bin/realesrgan...
    bin_realesrgan = os.path.join(bin_dir, REAL_ESRGAN_FILENAME)
    local_realesrgan = os.path.join(script_dir, REAL_ESRGAN_FILENAME)
    
    realesrgan_path = None
    if os.path.exists(bin_realesrgan):
        realesrgan_path = bin_realesrgan
    elif os.path.exists(local_realesrgan):
        realesrgan_path = local_realesrgan
    elif shutil.which(REAL_ESRGAN_FILENAME):
        realesrgan_path = REAL_ESRGAN_FILENAME
        
    if not realesrgan_path:
        print(f"错误: 未找到 {REAL_ESRGAN_FILENAME}。")
        print("请尝试以下解决方案之一：")
        print(f"1. 将 {REAL_ESRGAN_FILENAME} 及其 models 文件夹放入 'bin' 文件夹中。")
        print("2. 或将其所在目录添加到系统环境变量 PATH 中。")
        return None
    
    print(f"使用 Real-ESRGAN: {realesrgan_path}")
    return realesrgan_path

def process_file(file_path, realesrgan_path, output_dir=None):
    """处理单个图片文件"""
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 -> {file_path}")
        return

    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    
    # 防止重复处理已经处理过的文件
    if "_out" in name:
        print(f"跳过已处理文件: {filename}")
        return

    output_filename = f"{name}_out.png" # 强制输出为 png
    
    if output_dir:
        # 如果指定了输出目录，则使用该目录
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                print(f"创建输出目录失败: {e}")
                return
        output_path = os.path.join(output_dir, output_filename)
    else:
        # 否则保存在原目录
        output_path = os.path.join(os.path.dirname(file_path), output_filename)
    
    print(f"正在处理: {filename} -> {output_path}")

    # 构建 Real-ESRGAN 命令
    cmd = [
        realesrgan_path,
        "-i", file_path,
        "-o", output_path,
        "-n", MODEL_NAME,
        "-s", str(SCALE),
        "-f", "png" 
    ]
    
    # 关键：设置 cwd 为 exe 所在目录，以便找到 models
    cwd_path = os.path.dirname(realesrgan_path)
    if not cwd_path:
        cwd_path = None

    try:
        subprocess.run(cmd, check=True, cwd=cwd_path)
        if os.path.exists(output_path):
             print(f"处理完成: {output_path}")
        else:
             print(f"警告: 命令似乎成功但未生成 output 文件: {filename}")

    except subprocess.CalledProcessError as e:
        print(f"处理失败: {filename}")
        # print(e) # 简化输出，通常 RealESRGAN 会自己打印错误
    except Exception as e:
        print(f"发生未知错误: {e}")


def main():
    realesrgan_path = check_dependencies()
    if not realesrgan_path:
        sys.exit(1)

    output_dir = None

    # 获取拖拽的文件或命令行参数
    if len(sys.argv) > 1:
        input_paths = sys.argv[1:]
    else:
        # 如果没有参数，询问用户输入
        print("Process Image Super Resolution")
        user_input = input("请输入要处理的图片路径或文件夹路径 (多个路径用空格分隔): ")
        if not user_input.strip():
            print("未输入路径，程序退出。")
            return
        
        try:
            input_paths = shlex.split(user_input)
        except:
            input_paths = user_input.split()

        output_inp = input("请输入输出目录路径 (直接回车默认保存在原目录): ").strip()
        if output_inp:
            output_dir = output_inp.strip('"')

    for path in input_paths:
        # 去除可能的引号
        path = path.strip('"').strip("'")
        
        if os.path.exists(path) and os.path.isfile(path):
             # 检查是否是图片
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
                process_file(path, realesrgan_path, output_dir=output_dir)
            else:
                print(f"跳过非图片文件: {path}")

        elif os.path.exists(path) and os.path.isdir(path):
            print(f"正在扫描文件夹: {path}")
            # 处理文件夹内的图片
            extensions = ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp']
            unique_files = set()
            for ext in extensions:
                # Windows 上 glob 不区分大小写，但 Linux 区分，这里做个全集
                unique_files.update(glob.glob(os.path.join(path, ext)))
                unique_files.update(glob.glob(os.path.join(path, ext.upper())))
            
            files = sorted(list(unique_files))

            if not files:
                 print(f"文件夹内未找到图片: {path}")

            for file_path in files:
                process_file(file_path, realesrgan_path, output_dir=output_dir)
        else:
             print(f"无效路径: {path}")

    print("\n所有任务完成！")
    input("按回车键退出...")

if __name__ == "__main__":
    main()
