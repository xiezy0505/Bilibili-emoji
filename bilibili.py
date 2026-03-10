import requests
import os
import re

# --- 配置区域 ---
# ⚠️ 注意: 请不要将你的真实 SESSDATA 提交到 GitHub!
# 建议通过环境变量或本地配置文件读取
import os
SESSDATA = os.getenv("BILIBILI_SESSDATA", "YOUR_SESSDATA_HERE") 
# --- --- --- ---

url = "https://api.bilibili.com/x/emote/user/panel/web?business=reply"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": f"SESSDATA={SESSDATA}"
}

def download():
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data['code'] != 0:
            print(f"请求失败: {data['message']}")
            return

        packages = data['data']['packages']
        print(f"检测到 {len(packages)} 个表情包。")
        
        user_input = input("请输入要下载的表情包关键字(空格分隔，直接回车下载全部): ").strip()
        keywords = user_input.split() if user_input else []

        download_base_dir = input("请输入下载保存路径(直接回车默认为当前目录): ").strip()
        if not download_base_dir:
            download_base_dir = "."

        for pkg in packages:
            pkg_name = pkg['text']
            
            # 筛选特定的表情包：只要名字里包含这些词中的任意一个，就下载
            if keywords and not any(k in pkg_name for k in keywords):
                continue

            # 过滤掉文件夹名中的非法字符
            pkg_name = re.sub(r'[\\/:*?"<>|]', '', pkg_name)
            target_dir = os.path.join(download_base_dir, pkg_name)
            os.makedirs(target_dir, exist_ok=True)
            print(f"正在下载表情包: {pkg_name}")

            for e in pkg['emote']:
                if "动态" in pkg_name and 'gif_url' in e:
                    img_url = e['gif_url']
                else:
                    img_url = e['url']

                # 核心步骤：去掉 URL 末尾的 @ 符号及其后的缩略图参数，获取原图
                if "@" in img_url:
                    img_url = img_url.split("@")[0]
                
                img_name = e['text'].replace("[", "").replace("]", "")
                suffix = img_url.split(".")[-1]
                file_path = os.path.join(target_dir, f"{img_name}.{suffix}")

                img_data = requests.get(img_url).content
                with open(file_path, "wb") as f:
                    f.write(img_data)
            
            print(f"--- {pkg_name} 下载完成 ---")

    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    download()
    input("\n按回车键退出...")